from __future__ import annotations

import gc
import base64
import csv
import difflib
import html
import json
import multiprocessing
import os
import queue
import random
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.error
import urllib.request
import uuid
import warnings
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QPoint, QRectF, QSize, QThread, QTimer, Qt, QUrl, Signal
from PySide6.QtGui import (
    QColor, QFont, QFontMetrics, QIcon, QLinearGradient, QPainter, QPainterPath,
    QPen, QPixmap, QStandardItem, QStandardItemModel,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSplitter,
    QSpinBox,
    QStyle,
    QSplashScreen,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from config_store import (
    DEFAULTS,
    apply_settings,
    config_dir,
    config_path,
    load_settings,
    save_settings,
    save_tab_settings,
    tab_config_path,
)
from core import infer_speaking_direction, normalize_omnivoice_instruct, parse_input, parse_paragraph_segments
from diagnostics import gpu_snapshot, log_dir, log_event, log_path
from chatterbox_v3 import ChatterboxRenderWorker, ChatterboxV3Tab
from licensing import (
    activation_expiry,
    format_activation_code,
    hardware_request_id,
    is_activated,
    is_valid_activation_code,
    saved_activation_expiry,
    save_activation,
)


APP_NAME = "VIVU STUDIO"
APP_VERSION = "v1.0"
APP_USER_MODEL_ID = "TIMKEM.VoiceOverStudio"
DEFAULT_MODEL = "k2-fsa/OmniVoice"
DEFAULT_ZONOS2_MODEL = "Zyphra/ZONOS2"
DEFAULT_MOSS_MODEL = "OpenMOSS-Team/MOSS-TTS-Local-Transformer-v1.5"

# UI translations intentionally keep product names and technical terms such as
# Render, Token, CUDA, GPU, CPU, Whisper, SRT, MP3/WAV and model names intact.
VI_UI = {
    "Ready": "Sẵn sàng", "Minimize": "Thu nhỏ", "Maximize / Restore": "Phóng to / Khôi phục",
    "Close": "Đóng", "Voice List": "Danh sách giọng", "Voice Clone": "Nhân bản giọng",
    "Video Effect": "Hiệu ứng video", "Caption": "Phụ đề", "Watermark": "Dấu bản quyền",
    "Automation": "Tự động hóa", "Tools": "Công cụ", "Environment": "Môi trường",
    "Profile Manager": "Quản lý hồ sơ", "Voice Designer": "Thiết kế giọng",
    "Saved voice": "Giọng đã lưu", "Reference language": "Ngôn ngữ tham chiếu",
    "New profile name": "Tên hồ sơ mới", "Reference MP3/WAV": "MP3/WAV tham chiếu",
    "Reference transcript": "Bản chép lời tham chiếu", "Save voice profile": "Lưu hồ sơ giọng",
    "Preview voice": "Nghe thử giọng", "Delete voice": "Xóa giọng",
    "Auto transcript": "Tự động chép lời", "Create clone voices from tts-model": "Tạo giọng nhân bản từ tts-model",
    "Voice List Progress": "Tiến trình danh sách giọng", "Realtime processing log": "Nhật ký xử lý thời gian thực",
    "Render video effects": "Render hiệu ứng video", "Stop Video Effect": "Dừng hiệu ứng video",
    "Open output folder": "Mở thư mục đầu ra", "Random effects": "Hiệu ứng ngẫu nhiên",
    "Bounce motion": "Chuyển động nảy", "Merge segment videos": "Ghép các video đoạn",
    "Scratches": "Vết xước", "Dust specks": "Hạt bụi", "Film grain": "Hạt phim",
    "Flicker": "Nhấp nháy", "Vignette": "Tối góc", "Color fade": "Phai màu", "Scan lines": "Dòng quét",
    "English reference": "Tham chiếu tiếng Anh", "Vietnamese reference": "Tham chiếu tiếng Việt",
    "Auto detect": "Tự động nhận diện", "English": "Tiếng Anh", "Vietnamese": "Tiếng Việt",
    "French": "Tiếng Pháp", "German": "Tiếng Đức", "Spanish": "Tiếng Tây Ban Nha",
    "Italian": "Tiếng Ý", "Japanese": "Tiếng Nhật", "Mandarin": "Tiếng Trung", "Korean": "Tiếng Hàn",
    "Disabled": "Đã tắt", "Off": "Tắt", "Subtle": "Nhẹ", "Medium": "Vừa", "Heavy": "Mạnh", "Custom": "Tùy chỉnh",
    "Input": "Đầu vào", "Output": "Đầu ra", "Output folder": "Thư mục đầu ra",
    "Input file": "Tệp đầu vào", "Output format": "Định dạng đầu ra", "Language": "Ngôn ngữ",
    "Model": "Model", "Device": "Thiết bị", "Quality": "Chất lượng", "Width": "Chiều rộng",
    "Height": "Chiều cao", "Speed": "Tốc độ", "Duration": "Thời lượng", "Position": "Vị trí",
    "Font": "Phông chữ", "Font size": "Cỡ chữ", "Text color": "Màu chữ",
    "Background": "Nền", "Background color": "Màu nền", "Opacity": "Độ mờ",
    "Start": "Bắt đầu", "Stop": "Dừng", "Pause": "Tạm dừng", "Resume": "Tiếp tục",
    "Browse": "Chọn", "Add": "Thêm", "Remove": "Xóa", "Save": "Lưu", "Load": "Tải",
    "Reset": "Đặt lại", "Apply": "Áp dụng", "Cancel": "Hủy", "Yes": "Có", "No": "Không",
    "Settings": "Cài đặt", "Advanced settings": "Cài đặt nâng cao", "General": "Chung",
    "Progress": "Tiến trình", "Status": "Trạng thái", "Preview": "Xem trước",
    "Select all": "Chọn tất cả", "Clear all": "Bỏ chọn tất cả", "Overwrite existing files in selected range": "Ghi đè tệp hiện có trong phạm vi đã chọn",
    "Normalize completed batch after all segments render": "Chuẩn hóa lô hoàn tất sau khi Render tất cả đoạn",
    "Fit generated audio to each SRT timestamp duration": "Khớp âm thanh đã tạo với thời lượng từng mốc SRT",
    "Enable OmniVoice speaking style / instruct": "Bật phong cách nói / chỉ dẫn OmniVoice",
    "Apply direction to all segments": "Áp dụng chỉ dẫn cho mọi đoạn",
    "Auto per segment + base direction": "Tự động theo đoạn + chỉ dẫn cơ sở",
    "Default cloned voice": "Giọng nhân bản mặc định", "Warm, natural narration": "Giọng kể ấm áp, tự nhiên",
    "Calm documentary narration": "Giọng kể tài liệu điềm tĩnh", "Energetic advertisement": "Quảng cáo tràn đầy năng lượng",
    "Dramatic cinematic narration": "Giọng kể điện ảnh kịch tính", "Soft whisper": "Thì thầm nhẹ nhàng",
    "Elderly, measured delivery": "Giọng lớn tuổi, nhịp điệu chậm rãi",
    "Natural British English accent": "Giọng Anh tự nhiên",
    # Voice designer
    "Natural mode uses one formant-preserving pass plus gentle tone EQ. Keep Gender lock enabled; small adjustments sound substantially more realistic.": "Chế độ tự nhiên giữ formant và EQ nhẹ. Nên bật Khóa giới tính để giọng chân thực hơn.",
    "Source voice": "Giọng nguồn", "Preset": "Mẫu", "Gender range": "Giới tính",
    "Pitch shift": "Đổi cao độ", "Timbre / resonance": "Âm sắc / cộng hưởng",
    "Warmth": "Độ ấm", "Brightness": "Độ sáng", "Speaking speed": "Tốc độ nói",
    "Keep the variation within the same-gender range": "Giữ biến thể cùng giới tính",
    "Required: a new, unique profile name": "Bắt buộc: tên hồ sơ mới, không trùng",
    "Play original": "Nghe bản gốc", "Generate preview": "Tạo bản xem trước",
    "Play preview": "Nghe bản xem trước", "Save as new profile": "Lưu thành hồ sơ mới",
    # Voice Clone / V3
    "Voice Clone v3": "Nhân bản giọng v3", "Voice Clone V3": "Nhân bản giọng v3",
    "Voice and Input": "Giọng và đầu vào", "Voice profile": "Hồ sơ giọng",
    "Set default": "Đặt mặc định", "Batch Processing Queue": "Hàng đợi xử lý lô",
    "Batch Đang xử lý Queue": "Hàng đợi xử lý lô", "SRT/TXT input file": "Tệp SRT/TXT đầu vào",
    "+ Add Task Row": "+ Thêm dòng tác vụ", "+ Add batch task": "+ Thêm tác vụ lô",
    "Output and Audio": "Đầu ra và âm thanh", "Merge pause": "Khoảng nghỉ ghép",
    "Retry batch normalization": "Chuẩn hóa lại lô", "OmniVoice Configuration": "Cấu hình OmniVoice",
    "Checkpoint": "Checkpoint", "Diffusion steps": "Bước khuếch tán", "Compute device": "Thiết bị xử lý",
    "Preview segments": "Số đoạn xem thử", "Stability": "Độ ổn định", "Cooldown": "Nghỉ",
    "Reload every N segments": "Nạp lại mỗi N đoạn", "Speaking style": "Phong cách nói",
    "Direction mode": "Chế độ chỉ dẫn", "Segment override": "Ghi đè đoạn",
    "Set for selected": "Đặt cho mục chọn", "Clear selected": "Xóa mục chọn",
    "Render Range": "Phạm vi Render", "Segments": "Đoạn", "From": "Từ", "To": "Đến",
    "Render selected range": "Render phạm vi chọn", "Save Settings": "Lưu cài đặt",
    "Load defaults": "Tải mặc định", "Voice-over segments": "Các đoạn thuyết minh",
    "Paste one or more segments here. Separate segments with a blank line.": "Dán một hoặc nhiều đoạn tại đây. Ngăn cách bằng một dòng trống.",
    "Add text segments": "Thêm đoạn văn bản", "Time": "Thời gian", "Text": "Văn bản",
    "Status": "Trạng thái", "Direction": "Chỉ dẫn", "Actions": "Thao tác",
    "Processing and model download status will appear here.": "Trạng thái xử lý và tải model sẽ hiện tại đây.",
    "Voice": "Giọng", "Copy Voice": "Sao chép giọng", "Unload Model": "Gỡ Model",
    "Chatterbox Multilingual V3 Parameters": "Tham số Chatterbox đa ngôn ngữ V3",
    "Runtime": "Môi trường chạy", "Expression": "Biểu cảm", "Sampling": "Lấy mẫu",
    "Repeat": "Lặp", "Probability": "Xác suất", "ASR Quality Control": "Kiểm soát chất lượng ASR",
    "Options": "Tùy chọn", "Auto ASR repair": "Tự sửa ASR", "Overwrite existing": "Ghi đè tệp có sẵn",
    "Repair": "Số lần sửa", "ASR workers": "Luồng ASR", "Normalize audio folder": "Chuẩn hóa thư mục âm thanh",
    "Status filter": "Lọc trạng thái", "All files": "Tất cả tệp", "Render selected": "Render mục chọn",
    "Delete selected": "Xóa mục chọn", "Clear list": "Xóa danh sách",
    "Processing and model log": "Nhật ký xử lý và model", "Render batch V3": "Render lô V3",
    "Open output": "Mở đầu ra",
    # Video Effect
    "Input and Output": "Đầu vào và đầu ra", "Images": "Ảnh", "Audios": "Âm thanh",
    "+ Add Images / Audios / Output": "+ Thêm ảnh / âm thanh / đầu ra",
    "Check Images Folder": "Kiểm tra thư mục ảnh", "Check Video Output": "Kiểm tra video đầu ra",
    "Merge Video Output": "Ghép video đầu ra", "Frame": "Khung hình", "Size": "Kích thước",
    "Workers": "Luồng xử lý", "Pattern": "Kiểu chuyển động", "Motion": "Chuyển động",
    "Template": "Mẫu", "Save Template": "Lưu mẫu", "Zoom": "Thu phóng", "Face safe": "Giữ an toàn mặt",
    "Base crop": "Cắt cơ sở", "Edge reach": "Chạm biên", "Pre silence": "Im lặng đầu",
    "Min motion": "CĐ tối thiểu", "Combo radius": "Bán kính combo", "Offset X": "Lệch X",
    "Combo offset Y": "Lệch Y", "Retro Film": "Phim cổ điển",
    "Video Effect render log will appear here.": "Nhật ký Render hiệu ứng video sẽ hiện tại đây.",
    # Caption
    "Input and Mode": "Đầu vào và chế độ", "Tasks": "Tác vụ", "Source": "Nguồn", "Import": "Nhập",
    "+ Add caption task": "+ Thêm tác vụ phụ đề", "Config": "Cấu hình", "Save config": "Lưu cấu hình",
    "Local Recognition": "Nhận dạng cục bộ", "Caption mode": "Chế độ phụ đề", "Engine": "Engine",
    "Render": "Render", "Accuracy": "Độ chính xác", "GPU batch": "Lô GPU",
    "Word timing": "Mốc thời gian từ", "VAD filter": "Lọc VAD", "Punctuation": "Dấu câu",
    "Diarization": "Phân biệt người nói", "CapCut-style Presets": "Mẫu kiểu CapCut",
    "Notes": "Ghi chú", "Typography": "Kiểu chữ", "Style": "Kiểu", "Bold": "Đậm", "Italic": "Nghiêng",
    "Uppercase": "Viết hoa", "Two-line mode": "Chế độ 2 dòng", "Line wrap": "Xuống dòng",
    "Chars": "Ký tự", "Spacing": "Giãn cách", "Line": "Dòng", "Colors": "Màu sắc",
    "Active": "Đang chạy", "Refresh preview": "Làm mới xem trước", "Export config JSON": "Xuất cấu hình JSON",
    "Import SRT/JSON": "Nhập SRT/JSON", "Normalized caption config": "Cấu hình phụ đề chuẩn hóa",
    "Render captions": "Render phụ đề",
    # Watermark
    "Batch input (every video × every channel name)": "Đầu vào lô (mọi video × mọi tên kênh)",
    "Source videos": "Video nguồn", "Channel names": "Tên kênh", "Add videos": "Thêm video",
    "Trailer video": "Video trailer", "Copy path": "Sao chép đường dẫn", "Trailer transition": "Chuyển cảnh trailer",
    "Channel name style": "Kiểu tên kênh", "Position / style": "Vị trí / kiểu", "Channel name": "Tên kênh",
    "Edge padding X": "Lề X", "Opening warning (optional)": "Cảnh báo mở đầu (tùy chọn)",
    "Warning image": "Ảnh cảnh báo", "Display duration": "Thời gian hiển thị", "Fit": "Khớp",
    "YouTube subscribe overlay (optional)": "Lớp đăng ký YouTube (tùy chọn)",
    "Subscribe video": "Video đăng ký", "First show at": "Hiện lần đầu lúc", "Position / scale": "Vị trí / tỷ lệ",
    "Scale": "Tỷ lệ", "Chroma key": "Chroma key", "Key color": "Màu key", "Key tuning": "Tinh chỉnh key",
    "Blend": "Hòa trộn", "Color sampler": "Lấy mẫu màu", "Capture frame": "Chụp khung hình",
    "Realtime placement preview": "Xem trước vị trí thời gian thực", "Watermark tab ready.": "Tab dấu bản quyền đã sẵn sàng.",
    "Render batch": "Render lô", "Open folder": "Mở thư mục",
    # Automation / Tools / Environment
    "Shared sources": "Nguồn dùng chung", "Voice engine": "Engine giọng", "Group name": "Tên nhóm",
    "Group rows": "Nhóm các dòng", "Automation log": "Nhật ký tự động hóa",
    "Add automation input": "Thêm đầu vào", "Set trailer video": "Đặt video trailer",
    "Edit channel names": "Sửa tên kênh", "Set output folder": "Đặt thư mục đầu ra",
    "Save all": "Lưu tất cả", "Clear": "Xóa", "Render / Gen automation": "Render / Tạo tự động",
    "Remove video logo": "Xóa logo video", "Update missed storyboard prompts": "Cập nhật prompt storyboard thiếu",
    "Gemini trailer · Remove bottom-right logo": "Gemini trailer · Xóa logo góc dưới phải",
    "Logo region": "Vùng logo", "Inner margin": "Lề trong", "Analyze Preview": "Phân tích xem trước",
    "Remove Video Logo": "Xóa logo video", "Worst detected shot · Before / After": "Khung xấu nhất · Trước / Sau",
    "Before": "Trước", "After": "Sau", "Run Analyze & Preview to locate the strongest logo frame.": "Chạy Phân tích xem trước để tìm khung có logo rõ nhất.",
    "Tools ready.": "Công cụ đã sẵn sàng.", "HF token": "HF Token", "Gemini API key": "Khóa Gemini API",
    "Model cache": "Bộ nhớ đệm Model", "Optional: reserved for future script-processing features": "Tùy chọn: dành cho tính năng xử lý kịch bản sau này",
    "Optional model cache folder; blank uses Hugging Face default": "Tùy chọn: thư mục cache Model; để trống dùng mặc định Hugging Face",
    "Save settings": "Lưu cài đặt", "Open persistent log folder": "Mở thư mục nhật ký",
    "License Information": "Thông tin bản quyền", "License status": "Trạng thái bản quyền",
    "Request ID": "Request ID", "Expiration date": "Ngày hết hạn",
    "Time remaining": "Thời gian còn lại", "Activated": "Đã kích hoạt",
    "Copy": "Sao chép", "Copied": "Đã sao chép", "Expired": "Đã hết hạn",
    "Storyboard prompt TXT": "Prompt storyboard TXT", "Hide Number Table": "Ẩn bảng số",
    "Clear Selection": "Bỏ chọn", "Selected: 0 number(s)": "Đã chọn: 0 số",
    "Check Missing Images": "Kiểm tra ảnh thiếu", "Log": "Nhật ký", "Analyze & Preview": "Phân tích & xem trước",
    "Run Stable Clean": "Chạy Stable Clean", "View Stable Clean": "Xem Stable Clean",
    "View LaMa Fallback": "Xem LaMa dự phòng",
    "Use Stable Clean for Watermark": "Dùng Stable Clean cho dấu bản quyền",
    "Use LaMa Fallback for Watermark": "Dùng LaMa dự phòng cho dấu bản quyền",
    "Channel name starts": "Tên kênh bắt đầu", "Fast encoder": "Mã hóa nhanh",
    "Standard uses faster-whisper for SRT/JSON and burn-in.": "Standard dùng faster-whisper cho SRT/JSON và burn-in.",
    "Fix CUDA": "Sửa CUDA", "Edges": "Viền", "Shadow": "Bóng", "Inactive dim": "Làm mờ từ tĩnh",
    "Outline width": "Độ rộng viền", "Effects": "Hiệu ứng", "Pseudo glow": "Giả phát sáng",
    "Shadow offset": "Độ lệch bóng", "Glow strength": "Độ sáng", "Box mode": "Kiểu hộp",
    "Color": "Màu", "Padding": "Lề", "Corner radius": "Bo góc", "Type": "Loại",
    "Transition": "Chuyển tiếp", "Reveal words one-by-one": "Hiện từng từ",
    "Fade in words": "Làm rõ dần từng từ", "Pop active word": "Nhấn từ đang đọc",
    "Scale active": "Phóng từ đang đọc", "Anchor": "Neo", "Align": "Căn chỉnh", "Margins": "Lề",
    "Auto mode": "Chế độ tự động", "YouTube Auto Position": "Tự đặt vị trí YouTube",
    "Max": "Tối đa", "Grouping": "Cách nhóm", "Formats": "Định dạng", "Burned-in MP4": "MP4 gắn phụ đề",
    "Filename": "Tên tệp", "Motion template loaded: Hard Motion": "Đã tải mẫu chuyển động: Hard Motion",
    "Amount": "Mức", "Strength": "Cường độ", "Ready · Chatterbox Multilingual V3": "Sẵn sàng · Chatterbox đa ngôn ngữ V3",
    "Elapsed 00:00:00 · ETA waiting for the first segment": "Đã chạy 00:00:00 · ETA chờ đoạn đầu tiên",
    "Elapsed 00:00:00 · ETA waiting for first segment": "Đã chạy 00:00:00 · ETA chờ đoạn đầu tiên",
    "V3 officially supports 23 languages, but Vietnamese (vi) is not currently included. A Vietnamese reference can still provide voice timbre for cross-language cloning, but output must use a supported language ID and may retain the reference accent.": "V3 hỗ trợ 23 ngôn ngữ nhưng chưa có tiếng Việt (vi). Vẫn có thể dùng giọng Việt làm tham chiếu âm sắc, nhưng đầu ra phải chọn ngôn ngữ được hỗ trợ và có thể giữ âm giọng tham chiếu.",
    "ASR review / automatic repair queue": "Hàng đợi kiểm tra / tự sửa ASR", "Download / Load": "Tải / Nạp",
    "Compute": "Xử lý", "Dtype": "Dtype", "Attention": "Attention", "Max new tokens": "Token mới tối đa",
    "Auto duration guard (recommended — prevents runaway audio)": "Tự giới hạn thời lượng (khuyên dùng)",
    "Auto ASR check + rerender failed segments": "Tự kiểm tra ASR + Render lại đoạn lỗi",
    "Max QA retries": "Số lần QA tối đa", "Parallel ASR workers": "Luồng ASR song song",
    "Format": "Định dạng", "Render range": "Phạm vi Render", "Render all segments": "Render tất cả đoạn",
    "Check all audio (ASR)": "Kiểm tra toàn bộ âm thanh (ASR)", "Inputs": "Đầu vào",
    "Outline, Shadow, Glow": "Viền, bóng, phát sáng", "Background and Box": "Nền và hộp",
    "Highlight": "Làm nổi bật", "Timing and Line Breaking": "Thời gian và ngắt dòng", "Export": "Xuất",
    "MOSS-TTS Configuration": "Cấu hình MOSS-TTS", "TXT/SRT input": "Đầu vào TXT/SRT",
    "Failed / Review": "Lỗi / Cần duyệt", "Review required": "Cần duyệt", "Failed / Errors": "Lỗi",
    "Pending / Processing": "Chờ / Đang xử lý", "Verified / Completed": "Đã xác minh / Hoàn tất",
    "Optional: required for gated/private Hugging Face models": "Tùy chọn: cần cho model Hugging Face giới hạn/riêng tư",
    "One logo / channel name per line": "Mỗi dòng một logo / tên kênh",
    "Optional: trailer inserted before source video": "Tùy chọn: chèn trailer trước video nguồn",
    "Source video/audio": "Video/âm thanh nguồn", "Optional SRT/JSON": "SRT/JSON tùy chọn",
    "Leave blank to overwrite the selected voice transcript": "Để trống để ghi đè bản chép lời của giọng đã chọn",
    "Optional. Leave blank to let Whisper auto-transcribe.": "Tùy chọn. Để trống để Whisper tự chép lời.",
}

VI_PHRASES = (
    ("Open ", "Mở "), ("Select ", "Chọn "), ("Choose ", "Chọn "), ("Add ", "Thêm "),
    ("Remove ", "Xóa "), ("Delete ", "Xóa "), ("Save ", "Lưu "), ("Load ", "Tải "),
    ("Generate ", "Tạo "), ("Create ", "Tạo "), ("Start ", "Bắt đầu "), ("Stop ", "Dừng "),
    ("Input ", "Đầu vào "), ("Output ", "Đầu ra "), ("Reference ", "Tham chiếu "),
    ("Current ", "Hiện tại "), ("Selected ", "Đã chọn "), ("Default ", "Mặc định "),
    ("Processing ", "Đang xử lý "), ("Video ", "Video "), ("Audio ", "Âm thanh "),
    ("Voice ", "Giọng "), ("Caption ", "Phụ đề "), ("Watermark ", "Dấu bản quyền "),
    (" folder", " thư mục"), (" file", " tệp"), (" files", " tệp"), (" directory", " thư mục"),
    (" settings", " cài đặt"), (" preview", " xem trước"), (" progress", " tiến trình"),
    (" status", " trạng thái"), (" color", " màu"), (" size", " kích thước"),
)

VI_LOG_PHRASES = (
    (r"\bCompleted\b", "Hoàn tất"), (r"\bcompleted\b", "hoàn tất"),
    (r"\bFailed\b", "Thất bại"), (r"\bfailed\b", "thất bại"),
    (r"\bError\b", "Lỗi"), (r"\berror\b", "lỗi"),
    (r"\bStarting\b", "Đang bắt đầu"), (r"\bStarted\b", "Đã bắt đầu"),
    (r"\bProcessing\b", "Đang xử lý"), (r"\bLoading\b", "Đang nạp"),
    (r"\bLoaded\b", "Đã nạp"), (r"\bDownloading\b", "Đang tải"),
    (r"\bDownloaded\b", "Đã tải"), (r"\bSaving\b", "Đang lưu"),
    (r"\bSaved\b", "Đã lưu"), (r"\bVerified\b", "Đã xác minh"),
    (r"\bWaiting\b", "Đang chờ"), (r"\bwaiting\b", "đang chờ"),
    (r"\bSkipped\b", "Đã bỏ qua"), (r"\bskipped\b", "đã bỏ qua"),
    (r"\bDeleted\b", "Đã xóa"), (r"\bRemoved\b", "Đã loại bỏ"),
    (r"\bRetrying\b", "Đang thử lại"), (r"\bRetry\b", "Thử lại"),
    (r"\bReady\b", "Sẵn sàng"), (r"\bCancelled\b", "Đã hủy"),
    (r"\bsegment(s)?\b", "đoạn"), (r"\bfile(s)?\b", "tệp"),
    (r"\bfolder\b", "thư mục"), (r"\bselected\b", "đã chọn"),
    (r"\bsource\b", "nguồn"), (r"\bdestination\b", "đích"),
    (r"\bduration\b", "thời lượng"), (r"\belapsed\b", "đã chạy"),
    (r"\bremaining\b", "còn lại"), (r"\bnot found\b", "không tìm thấy"),
    (r"\bdoes not exist\b", "không tồn tại"), (r"\binvalid\b", "không hợp lệ"),
    (r"\bcreated\b", "đã tạo"), (r"\busing\b", "đang dùng"),
)


class TranslatedLogEdit(QPlainTextEdit):
    """A log view that retains raw English and renders it in the active UI language."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._source_paragraphs: list[str] = []

    def _display(self, text: str) -> str:
        translator = getattr(self.window(), "translated_log_text", None)
        return translator(text) if callable(translator) else text

    def appendPlainText(self, text: str) -> None:
        source = str(text)
        self._source_paragraphs.append(source)
        super().appendPlainText(self._display(source))

    def setPlainText(self, text: str) -> None:
        source = str(text)
        self._source_paragraphs = [source] if source else []
        super().setPlainText(self._display(source))

    def clear(self) -> None:
        self._source_paragraphs.clear()
        super().clear()

    def retranslate(self) -> None:
        super().setPlainText("\n".join(self._display(text) for text in self._source_paragraphs))
MOSS_CHECKPOINT_OPTIONS = (
    (
        "MOSS-TTS Local v1.5 · 5B · 48 kHz stereo · 31 languages",
        "OpenMOSS-Team/MOSS-TTS-Local-Transformer-v1.5",
        "Best quality and multilingual coverage. Uses MOSS-Audio-Tokenizer-v2.",
    ),
    (
        "MOSS-TTS Local v1.0 Lite · 1.7B · 24 kHz mono · 20 languages",
        "OpenMOSS-Team/MOSS-TTS-Local-Transformer",
        "Lighter and faster to load. English voice cloning is supported; Vietnamese is not officially supported.",
    ),
)
_MOSS_RUNTIME_CACHE: dict[str, object] = {}
APP_ROOT = Path(__file__).resolve().parent
APP_RUNTIME_ROOT = Path(getattr(sys, "_MEIPASS", APP_ROOT))
APP_ICON = APP_ROOT / "assets" / "voice.ico"
PIPER_MODEL_DIR = APP_ROOT / "tts-model"
VIDEO_EFFECT_SCRIPT = APP_RUNTIME_ROOT / "image_audio_motion_pipeline_v9.pyc"
VIDEO_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
VIDEO_AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}
VIDEO_FILE_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
VIDEO_QUALITY_PRESETS = {
    "HD": 720,
    "FHD": 1080,
    "2K": 1440,
    "4K": 2160,
}


def moss_expected_duration(text: str) -> float:
    """Estimate natural narration length and include explicit MOSS pause tags."""
    pauses = sum(
        float(value) for value in re.findall(r"\[pause\s+([0-9]+(?:\.[0-9]+)?)s\]", text, re.IGNORECASE)
    )
    spoken = re.sub(r"\[pause\s+[0-9]+(?:\.[0-9]+)?s\]", " ", text, flags=re.IGNORECASE)
    words = re.findall(r"[\w]+(?:['’][\w]+)?", spoken, re.UNICODE)
    punctuation = 0.12 * len(re.findall(r"[,;:]", spoken))
    punctuation += 0.24 * len(re.findall(r"[.!?]", spoken))
    return max(0.8, len(words) / 2.5 + punctuation + pauses)


def normalized_speech_text(text: str) -> str:
    text = re.sub(r"\[pause\s+[0-9]+(?:\.[0-9]+)?s\]", " ", text, flags=re.IGNORECASE)
    return " ".join(re.findall(r"[\w]+(?:['’][\w]+)?", text.lower(), re.UNICODE))


def cached_hf_snapshot(repo_id: str) -> str:
    cache_name = "models--" + repo_id.replace("/", "--")
    roots: list[Path] = []
    hf_home = os.environ.get("HF_HOME", "").strip()
    if hf_home:
        roots.append(Path(hf_home) / "hub")
    roots.append(APP_ROOT / "cache" / "huggingface" / "hub")
    for root in roots:
        model_root = root / cache_name
        ref = model_root / "refs" / "main"
        if ref.is_file():
            revision = ref.read_text(encoding="utf-8").strip()
            snapshot = model_root / "snapshots" / revision
            if snapshot.is_dir():
                return str(snapshot)
    return repo_id
CAPTION_PRESET_ORDER = [
    "Classic White Orange",
    "Orange Box Active",
    "Soft Dark Strip",
    "Bold Creator",
    "Minimal Clean",
]
CAPTION_STYLE_PRESETS = {
    "Classic White Orange": {
        "note": "White text, black outline, orange active word, no background.",
        "mode": "Standard",
        "font_family": "Montserrat",
        "font_size": 54,
        "bold": True,
        "italic": False,
        "uppercase": False,
        "base_color": "#FFFFFF",
        "active_color": "#FF8A00",
        "outline_color": "#000000",
        "outline_width": 3,
        "shadow": True,
        "shadow_color": "#000000",
        "background_mode": "None",
        "background_color": "#000000",
        "background_opacity": 45,
        "highlight_type": "Active color",
        "highlight_transition": "Instant",
        "reveal_words": False,
        "scale_active_word": 100,
        "anchor": "Bottom",
        "alignment": "Center",
        "margin_bottom": 90,
    },
    "Orange Box Active": {
        "note": "White text with black outline; the active word sits on an orange box.",
        "mode": "Pro Highlight",
        "font_family": "Montserrat",
        "font_size": 56,
        "bold": True,
        "italic": False,
        "uppercase": False,
        "base_color": "#FFFFFF",
        "active_color": "#FFFFFF",
        "outline_color": "#000000",
        "outline_width": 3,
        "shadow": True,
        "shadow_color": "#000000",
        "background_mode": "Active word box",
        "background_color": "#FF8A00",
        "background_opacity": 90,
        "highlight_type": "Active background",
        "highlight_transition": "Smooth",
        "reveal_words": True,
        "scale_active_word": 104,
        "anchor": "Bottom",
        "alignment": "Center",
        "margin_bottom": 90,
    },
    "Soft Dark Strip": {
        "note": "A soft dark strip behind the whole line with orange active word.",
        "mode": "Standard",
        "font_family": "Poppins",
        "font_size": 50,
        "bold": True,
        "italic": False,
        "uppercase": False,
        "base_color": "#FFFFFF",
        "active_color": "#FF9D2E",
        "outline_color": "#000000",
        "outline_width": 2,
        "shadow": True,
        "shadow_color": "#000000",
        "background_mode": "Line box",
        "background_color": "#000000",
        "background_opacity": 55,
        "highlight_type": "Active color",
        "highlight_transition": "Smooth",
        "reveal_words": False,
        "scale_active_word": 100,
        "anchor": "Bottom",
        "alignment": "Center",
        "margin_bottom": 100,
    },
    "Bold Creator": {
        "note": "Thick outline, strong shadow, bright creator-style active word.",
        "mode": "Pro Highlight",
        "font_family": "Anton",
        "font_size": 60,
        "bold": True,
        "italic": False,
        "uppercase": True,
        "base_color": "#FFFFFF",
        "active_color": "#FFB000",
        "outline_color": "#000000",
        "outline_width": 5,
        "shadow": True,
        "shadow_color": "#000000",
        "background_mode": "None",
        "background_color": "#000000",
        "background_opacity": 45,
        "highlight_type": "Progressive sweep",
        "highlight_transition": "Sweep",
        "reveal_words": True,
        "scale_active_word": 108,
        "anchor": "Bottom",
        "alignment": "Center",
        "margin_bottom": 85,
    },
    "Minimal Clean": {
        "note": "Clean white subtitle, thin outline, soft warm active color.",
        "mode": "Standard",
        "font_family": "Arial",
        "font_size": 46,
        "bold": True,
        "italic": False,
        "uppercase": False,
        "base_color": "#FFFFFF",
        "active_color": "#FFD166",
        "outline_color": "#111111",
        "outline_width": 1,
        "shadow": False,
        "shadow_color": "#000000",
        "background_mode": "None",
        "background_color": "#000000",
        "background_opacity": 35,
        "highlight_type": "Active color",
        "highlight_transition": "Instant",
        "reveal_words": False,
        "scale_active_word": 100,
        "anchor": "Bottom",
        "alignment": "Center",
        "margin_bottom": 80,
    },
}
PIPER_REFERENCE_TEXTS = {
    "vi": (
        "Xin chào. Đây là giọng đọc mẫu rõ ràng và tự nhiên. Hôm nay chúng ta cùng nghe một câu "
        "chuyện nhẹ nhàng, với nhịp đọc đều đặn, âm lượng ổn định và cách phát âm dễ nghe. "
        "Những từ tiếp theo giúp hệ thống ghi nhớ đầy đủ đặc điểm riêng của giọng nói này."
    ),
    "en": (
        "Hello. This is a clear and natural reference voice. Today we are reading a gentle story "
        "at a steady pace, with consistent volume and careful pronunciation. The following words "
        "help the system remember the unique character, rhythm, and tone of this speaker."
    ),
    "id": (
        "Halo. Ini adalah contoh suara yang jelas dan alami. Hari ini kita membaca sebuah cerita "
        "dengan irama yang stabil, volume yang konsisten, dan pengucapan yang mudah didengar. "
        "Kata berikut membantu sistem mengingat karakter suara pembicara ini."
    ),
}


def piper_config_language(config: dict) -> str:
    language_code = str(config.get("language", {}).get("code", "")).strip()
    espeak_voice = str(config.get("espeak", {}).get("voice", "")).strip()
    value = (language_code or espeak_voice or "vi").lower().replace("-", "_")
    return value.split("_", 1)[0]


OMNIVOICE_MODEL_CACHE: dict[tuple[str, str], object] = {}
OMNIVOICE_MODEL_LOADING: dict[tuple[str, str], threading.Event] = {}
OMNIVOICE_MODEL_ERRORS: dict[tuple[str, str], BaseException] = {}
OMNIVOICE_MODEL_LOCK = threading.RLock()


def setting_bool(settings: dict[str, str], key: str) -> bool:
    return settings.get(key, DEFAULTS[key]).lower() in {"1", "true", "yes", "on"}


def setting_int(settings: dict[str, str], key: str) -> int:
    try:
        return int(settings.get(key, DEFAULTS[key]))
    except ValueError:
        return int(DEFAULTS[key])


def ffmpeg_executable() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def ffprobe_executable() -> str:
    ffmpeg_path = Path(ffmpeg_executable())
    sibling = ffmpeg_path.with_name("ffprobe.exe" if sys.platform == "win32" else "ffprobe")
    if sibling.is_file():
        return str(sibling)
    found = shutil.which("ffprobe.exe" if sys.platform == "win32" else "ffprobe")
    return found or ""


def configure_ffmpeg() -> str:
    executable = ffmpeg_executable()
    directory = str(Path(executable).parent)
    path_entries = os.environ.get("PATH", "").split(os.pathsep)
    if directory not in path_entries:
        os.environ["PATH"] = directory + os.pathsep + os.environ.get("PATH", "")
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Couldn't find ffmpeg or avconv.*")
        from pydub import AudioSegment

    AudioSegment.converter = executable
    AudioSegment.ffmpeg = executable
    return executable


def available_video_gpu_codec() -> str:
    try:
        result = subprocess.run(
            [ffmpeg_executable(), "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=0x08000000 if sys.platform == "win32" else 0,
        )
        output = result.stdout + result.stderr
    except Exception:
        return ""
    for candidate in ("h264_nvenc", "hevc_nvenc", "h264_qsv", "h264_amf"):
        if candidate in output:
            return candidate
    return ""


def require_video_gpu_codec() -> str:
    codec = available_video_gpu_codec()
    if not codec:
        raise RuntimeError(
            "No supported GPU video encoder was found. "
            "Install/update the NVIDIA, Intel, or AMD graphics driver, "
            "then restart the app."
        )
    return codec


def preferred_video_effect_codec(saved_codec: str) -> str:
    if saved_codec == "libx264" and available_video_gpu_codec():
        return "auto"
    return saved_codec or "auto"


CUDA_DLL_DIRECTORY_HANDLES: list[object] = []
CUDA_DLL_DIRECTORIES_ADDED: set[str] = set()


def caption_cuda_runtime_dirs() -> list[Path]:
    site_root = Path(sys.prefix) / "Lib" / "site-packages" / "nvidia"
    candidates = []
    for package_dir in ("cublas", "cudnn", "cuda_runtime"):
        for child in ("bin", "lib"):
            candidates.append(site_root / package_dir / child)
    return [path for path in candidates if path.is_dir()]


def configure_caption_cuda_runtime_paths() -> list[Path]:
    paths = caption_cuda_runtime_dirs()
    if not paths:
        return []
    current_path = os.environ.get("PATH", "").split(os.pathsep)
    additions = [str(path) for path in paths if str(path) not in current_path]
    if additions:
        os.environ["PATH"] = os.pathsep.join(additions + current_path)
    if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
        for path in paths:
            path_text = str(path)
            if path_text not in CUDA_DLL_DIRECTORIES_ADDED:
                try:
                    CUDA_DLL_DIRECTORY_HANDLES.append(os.add_dll_directory(path_text))
                    CUDA_DLL_DIRECTORIES_ADDED.add(path_text)
                except OSError:
                    pass
    return paths


def missing_caption_cuda_packages() -> list[str]:
    site_root = Path(sys.prefix) / "Lib" / "site-packages" / "nvidia"
    cublas_ok = any((site_root / "cublas").glob("**/cublas64_12.dll"))
    cudnn_ok = any((site_root / "cudnn").glob("**/cudnn*.dll"))
    missing = []
    if not cublas_ok:
        missing.append("nvidia-cublas-cu12")
    if not cudnn_ok:
        missing.append("nvidia-cudnn-cu12")
    return missing


def caption_transcribe_process(options: dict, result_queue) -> None:
    try:
        configure_caption_cuda_runtime_paths()
        from faster_whisper import BatchedInferencePipeline, WhisperModel

        device = options["device"]
        model = WhisperModel(
            options["model_name"],
            device=device,
            compute_type="float16" if device == "cuda" else "int8",
            num_workers=max(1, int(options.get("workers", 4 if device == "cuda" else 2))),
        )
        transcriber = BatchedInferencePipeline(model=model) if device == "cuda" else model
        transcribe_options = {
            "language": options["language"],
            "beam_size": options["beam_size"],
            "vad_filter": options["vad_filter"],
            "word_timestamps": options["word_timestamps"],
        }
        if device == "cuda":
            transcribe_options.update(
                {
                    "batch_size": int(options.get("batch_size", 16)),
                    "without_timestamps": False,
                }
            )
        raw_segments, _ = transcriber.transcribe(options["source_path"], **transcribe_options)
        parsed_segments = []
        for raw in raw_segments:
            words = [
                {
                    "text": word.word.strip(),
                    "start": float(word.start),
                    "end": float(word.end),
                }
                for word in (raw.words or [])
                if word.word.strip()
            ]
            text = str(raw.text).strip()
            if text:
                parsed_segments.append(
                    {
                        "start": float(raw.start),
                        "end": float(raw.end),
                        "text": text,
                        "words": words,
                    }
                )
            result_queue.put(
                (
                    "progress",
                    {
                        "count": len(parsed_segments),
                        "end": float(raw.end or 0.0),
                    },
                )
            )
        result_queue.put(("completed", parsed_segments))
    except Exception:
        result_queue.put(("error", traceback.format_exc()))


def zonos2_connection_error(server_url: str) -> str:
    return (
        f"Cannot connect to the ZONOS2 server at {server_url}.\n\n"
        "The selected local clone voice is ready, but ZONOS2 must be running separately "
        "before Preview or Render can generate audio.\n\n"
        "This computer currently needs a Linux/WSL ZONOS2 server listening on port 1919. "
        "After starting it, click Refresh beside Voice, then render again."
    )


def voice_display_name(name: str) -> str:
    return name.removeprefix("Local clone: ").removeprefix("Piper - ")


def next_audio_variant_suffix(output_dir: Path, total: int, output_format: str) -> str:
    width = max(3, len(str(total)))
    index = 0
    while True:
        index += 1
        value = index
        letters = ""
        while value:
            value, remainder = divmod(value - 1, 26)
            letters = chr(ord("a") + remainder) + letters
        suffix = f"-{letters}"
        if not any(
            (output_dir / f"{position:0{width}d}{suffix}.{output_format}").exists()
            for position in range(1, total + 1)
        ):
            return suffix


def load_cached_omnivoice(
    model_name: str,
    device_mode: str,
    wait_progress=None,
    wait_timeout_seconds: int = 600,
):
    key = (model_name, device_mode)
    loader_event: threading.Event | None = None
    is_loader = False
    started_waiting = time.monotonic()
    with OMNIVOICE_MODEL_LOCK:
        if key in OMNIVOICE_MODEL_CACHE:
            return OMNIVOICE_MODEL_CACHE[key]
        loader_event = OMNIVOICE_MODEL_LOADING.get(key)
        if loader_event is None:
            loader_event = threading.Event()
            OMNIVOICE_MODEL_LOADING[key] = loader_event
            OMNIVOICE_MODEL_ERRORS.pop(key, None)
            is_loader = True

    if not is_loader:
        while True:
            with OMNIVOICE_MODEL_LOCK:
                if key in OMNIVOICE_MODEL_CACHE:
                    return OMNIVOICE_MODEL_CACHE[key]
                error = OMNIVOICE_MODEL_ERRORS.get(key)
                if error is not None:
                    raise RuntimeError(f"OmniVoice preload failed: {error}") from error
            elapsed = int(time.monotonic() - started_waiting)
            if wait_progress and (elapsed == 0 or elapsed % 15 == 0):
                wait_progress(
                    f"OmniVoice checkpoint is already loading in the background; "
                    f"waiting {elapsed}s..."
                )
            if elapsed >= wait_timeout_seconds:
                raise TimeoutError(
                    "OmniVoice preload is taking too long and may be stuck in the Hugging Face cache. "
                    "Restart the app and render again. The app now disables Hugging Face Xet to avoid "
                    "this Windows cache stall."
                )
            loader_event.wait(timeout=1)

    try:
        log_event(
            f"OMNIVOICE | loading | model={model_name} | device={device_mode} | "
            f"HF_HOME={os.environ.get('HF_HOME', '')} | "
            f"HF_HUB_DISABLE_XET={os.environ.get('HF_HUB_DISABLE_XET', '')}"
        )
        import torch
        from omnivoice import OmniVoice

        dtype = torch.float16 if device_mode == "cuda" else torch.float32
        device_map = "cuda:0" if device_mode == "cuda" else "cpu"
        model = OmniVoice.from_pretrained(model_name, device_map=device_map, dtype=dtype)
        with OMNIVOICE_MODEL_LOCK:
            OMNIVOICE_MODEL_CACHE[key] = model
        log_event(f"OMNIVOICE | loaded | model={model_name} | device={device_mode}")
        return model
    except BaseException as exc:
        with OMNIVOICE_MODEL_LOCK:
            OMNIVOICE_MODEL_ERRORS[key] = exc
        raise
    finally:
        with OMNIVOICE_MODEL_LOCK:
            OMNIVOICE_MODEL_LOADING.pop(key, None)
        loader_event.set()


def clear_cached_omnivoice(model_name: str, device_mode: str) -> None:
    with OMNIVOICE_MODEL_LOCK:
        key = (model_name, device_mode)
        OMNIVOICE_MODEL_CACHE.pop(key, None)
        OMNIVOICE_MODEL_ERRORS.pop(key, None)


def app_data_dir() -> Path:
    path = config_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


class ProfileStore:
    def __init__(self) -> None:
        self.root = app_data_dir() / "profiles"
        self.root.mkdir(parents=True, exist_ok=True)

    def names(self) -> list[str]:
        return sorted(path.name for path in self.root.iterdir() if path.is_dir())

    def load(self, name: str) -> dict:
        profile_dir = self.root / name
        profile = json.loads((profile_dir / "profile.json").read_text(encoding="utf-8"))
        # Bundled profiles must remain portable when the customer extracts the
        # app to a different drive or folder.
        local_reference = profile_dir / "reference.wav"
        if local_reference.is_file():
            profile["reference_audio"] = str(local_reference)
        local_originals = sorted(profile_dir.glob("original_reference.*"))
        if local_originals:
            profile["original_reference_audio"] = str(local_originals[0])
        return profile

    def delete(self, name: str) -> None:
        profile_dir = (self.root / name).resolve()
        if profile_dir.parent != self.root.resolve() or not profile_dir.is_dir():
            raise ValueError("Voice profile does not exist.")
        shutil.rmtree(profile_dir)

    def update_transcript(self, name: str, transcript: str) -> dict:
        transcript = transcript.strip()
        if not transcript:
            raise ValueError("Transcript cannot be empty.")
        profile_dir = (self.root / name).resolve()
        if profile_dir.parent != self.root.resolve() or not profile_dir.is_dir():
            raise ValueError("Voice profile does not exist.")
        profile_path = profile_dir / "profile.json"
        if not profile_path.is_file():
            raise ValueError("Voice profile data is missing.")
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        profile["reference_text"] = transcript
        profile["transcript_updated_at"] = datetime.now(timezone.utc).isoformat()
        profile_path.write_text(
            json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return profile

    def save_designed_variant(
        self, name: str, preview_audio: Path, source_profile: dict, design: dict
    ) -> dict:
        safe_name = re.sub(r"[^A-Za-z0-9 _.-]", "_", name).strip(" .")
        if not safe_name:
            raise ValueError("New voice profile name is required.")
        destination = self.root / safe_name
        if destination.exists():
            raise ValueError("A voice profile with this name already exists.")
        if not preview_audio.is_file():
            raise ValueError("Generate a voice preview before saving the new profile.")
        destination.mkdir(parents=True)
        reference_audio = destination / "reference.wav"
        shutil.copy2(preview_audio, reference_audio)
        profile = {
            "name": safe_name,
            "reference_audio": str(reference_audio),
            "reference_text": str(source_profile.get("reference_text", "")),
            "language": str(source_profile.get("language", "en")),
            "source_profile": str(source_profile.get("name", "")),
            "voice_design": design,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        (destination / "profile.json").write_text(
            json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return profile

    def save(
        self, name: str, source_audio: Path, transcript: str, language: str = "en", progress=None
    ) -> dict:
        progress = progress or (lambda message: None)
        safe_name = re.sub(r"[^A-Za-z0-9 _.-]", "_", name).strip(" .")
        if not safe_name:
            raise ValueError("Voice profile name is required.")
        destination = self.root / safe_name
        destination.mkdir(parents=True, exist_ok=True)
        managed_source = destination / f"original_reference{source_audio.suffix.lower() or '.audio'}"
        try:
            if source_audio.resolve() != managed_source.resolve():
                shutil.copy2(source_audio, managed_source)
        except OSError:
            shutil.copy2(source_audio, managed_source)
        normalized = destination / "reference.wav"
        progress("Normalizing reference audio with FFmpeg...")
        normalize_reference(managed_source, normalized)
        if transcript.strip():
            progress("Using the supplied reference transcript.")
        else:
            progress("Downloading/loading faster-whisper. First use can take several minutes...")
            transcript = transcribe_reference(normalized, language, progress)
        progress("Writing reusable voice profile...")
        profile = {
            "name": safe_name,
            "reference_audio": str(normalized),
            "original_reference_audio": str(managed_source),
            "reference_text": transcript,
            "language": language,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        (destination / "profile.json").write_text(
            json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return profile


def normalize_reference(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise ValueError("Reference audio file does not exist.")
    command = [
        ffmpeg_executable(),
        "-y",
        "-i",
        str(source),
        "-ac",
        "1",
        "-ar",
        "24000",
        "-af",
        "highpass=f=70,lowpass=f=11000,loudnorm=I=-20:TP=-2:LRA=7",
        str(destination),
    ]
    result = subprocess.run(command, capture_output=True, text=True, creationflags=0x08000000)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed to normalize reference audio:\n{result.stderr[-1000:]}")


def voice_design_audio_filter(settings: dict) -> str:
    pitch = float(settings.get("pitch_semitones", 0.0))
    timbre = float(settings.get("formant_semitones", 0.0))
    speed = float(settings.get("speed", 1.0))
    warmth = float(settings.get("warmth_db", 0.0))
    brightness = float(settings.get("brightness_db", 0.0))
    pitch_ratio = 2.0 ** (pitch / 12.0)
    filters = ["highpass=f=65"]
    if abs(pitch) >= 0.05 or abs(speed - 1.0) >= 0.005:
        filters.append(
            f"rubberband=tempo={speed:.6f}:pitch={pitch_ratio:.6f}:"
            # A long analysis window with crisp transients leaves audible pre-echo on
            # speech, especially around Vietnamese consonants.  The short, soft setup
            # keeps the formant-preserving pitch shift but avoids the metallic tail and
            # joins adjacent analysis frames more smoothly.
            "transients=mixed:detector=soft:phase=laminar:window=short:"
            "smoothing=on:formant=preserved:pitchq=quality:channels=together"
        )
    # Independent formant shifting needs a second spectral transformation and can make
    # speech sound metallic. Stage 1 therefore treats this as a gentle resonance/timbre
    # control using complementary low-mid and presence EQ while preserving formants.
    if abs(timbre) >= 0.05:
        filters.append(f"equalizer=f=320:t=q:w=1.0:g={-timbre * 0.7:.2f}")
        filters.append(f"equalizer=f=2600:t=q:w=1.0:g={timbre * 0.7:.2f}")
    if abs(warmth) >= 0.05:
        filters.append(f"lowshelf=f=220:g={warmth:.2f}")
    if abs(brightness) >= 0.05:
        filters.append(f"highshelf=f=3500:g={brightness:.2f}")
    filters.extend(["lowpass=f=11000", "loudnorm=I=-20:TP=-2:LRA=7"])
    return ",".join(filters)


def render_voice_design_preview(
    source: Path, destination: Path, settings: dict, progress=None
) -> Path:
    progress = progress or (lambda message: None)
    if not source.is_file():
        raise ValueError("The selected source voice audio is missing.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    progress("Applying pitch, formant, tone, and speed adjustments...")
    result = subprocess.run(
        [
            ffmpeg_executable(), "-y", "-i", str(source), "-vn",
            "-af", voice_design_audio_filter(settings),
            "-ac", "1", "-ar", "24000", "-codec:a", "pcm_s16le",
            str(destination),
        ],
        capture_output=True,
        text=True,
        creationflags=0x08000000,
    )
    if result.returncode != 0 or not destination.is_file():
        destination.unlink(missing_ok=True)
        raise RuntimeError(f"Could not generate voice design preview:\n{result.stderr[-2000:]}")
    progress("Voice design preview is ready.")
    return destination


def measure_speech_rms_db(path: Path, threshold_db: float = -45.0) -> float | None:
    import numpy as np

    result = subprocess.run(
        [
            ffmpeg_executable(), "-v", "error", "-i", str(path),
            "-ac", "1", "-ar", "24000", "-f", "f32le", "-",
        ],
        capture_output=True,
        creationflags=0x08000000,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Could not measure audio loudness:\n{result.stderr[-1000:]}")
    audio = np.frombuffer(result.stdout, dtype=np.float32)
    frame_size = 480
    frame_count = len(audio) // frame_size
    if not frame_count:
        return None
    frames = audio[: frame_count * frame_size].reshape(frame_count, frame_size)
    frame_rms = np.sqrt(np.mean(frames * frames, axis=1))
    active = frames[frame_rms > 10 ** (threshold_db / 20)]
    if not len(active):
        return None
    rms = float(np.sqrt(np.mean(active * active)))
    return 20 * float(np.log10(max(rms, 1e-9)))


def apply_constant_gain(path: Path, gain_db: float) -> None:
    temporary = path.with_name(f".{path.stem}.batch-normalized{path.suffix}")
    codec = ["-codec:a", "pcm_s16le"] if path.suffix.lower() == ".wav" else [
        "-codec:a", "libmp3lame", "-b:a", "192k"
    ]
    result = subprocess.run(
        [
            ffmpeg_executable(), "-y", "-i", str(path), "-af",
            f"volume={gain_db:.3f}dB,alimiter=limit=0.891:level=false:latency=true",
            *codec, str(temporary),
        ],
        capture_output=True,
        text=True,
        creationflags=0x08000000,
    )
    if result.returncode != 0:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"Batch audio normalization failed:\n{result.stderr[-1000:]}")
    try:
        os.replace(temporary, path)
    except PermissionError as exc:
        temporary.unlink(missing_ok=True)
        raise PermissionError(
            f"Cannot update '{path.name}' because it is open in another application. "
            "Close the audio player, then click Retry batch normalization."
        ) from exc


def normalize_completed_batch(
    files: list[Path],
    progress=None,
    cancelled=None,
    target_db: float = -20.0,
    originals_dir: Path | None = None,
    original_files: list[Path] | None = None,
    report_path: Path | None = None,
) -> list[dict]:
    progress = progress or (lambda message: None)
    cancelled = cancelled or (lambda: False)
    originals_dir = originals_dir or files[0].parent / "_original_omnivoice"
    originals_dir.mkdir(parents=True, exist_ok=True)
    archive_files = files if original_files is None else original_files
    for index, path in enumerate(archive_files, start=1):
        progress(f"Saving original OmniVoice file {index}/{len(archive_files)}: {path.name}")
        shutil.copy2(path, originals_dir / path.name)
    measurements: list[tuple[Path, float]] = []
    for index, path in enumerate(files, start=1):
        if cancelled():
            raise InterruptedError("Batch normalization cancelled.")
        progress(f"Measuring speech loudness {index}/{len(files)}: {path.name}")
        level = measure_speech_rms_db(path)
        if level is not None:
            measurements.append((path, level))
    report: list[dict] = []
    for index, (path, level) in enumerate(measurements, start=1):
        if cancelled():
            raise InterruptedError("Batch normalization cancelled.")
        gain_db = max(-12.0, min(12.0, target_db - level))
        original_path = originals_dir / path.name
        original_level = measure_speech_rms_db(original_path) if original_path.is_file() else level
        status = "already near target"
        if abs(gain_db) < 0.75:
            progress(
                f"Batch file already near target {index}/{len(measurements)}: {path.name}"
            )
            applied_gain = 0.0
        else:
            progress(
                f"Normalizing completed batch {index}/{len(measurements)}: "
                f"{path.name} ({gain_db:+.1f} dB)"
            )
            apply_constant_gain(path, gain_db)
            applied_gain = gain_db
            status = "normalized"
        report.append(
            {
                "file": path.name,
                "original_speech_rms_db": round(original_level, 3),
                "before_pass_speech_rms_db": round(level, 3),
                "gain_db": round(applied_gain, 3),
                "after_speech_rms_db": round(measure_speech_rms_db(path), 3),
                "status": status,
                "original_file": str(original_path),
            }
        )
    report_path = report_path or files[0].parent / "loudness_before_after.csv"
    with report_path.open("w", encoding="utf-8-sig", newline="") as report_file:
        writer = csv.DictWriter(report_file, fieldnames=list(report[0]) if report else ["file"])
        writer.writeheader()
        writer.writerows(report)
    progress(f"Before/after loudness report saved: {report_path.name}")
    return report


def ffmpeg_concat_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/").replace("'", r"'\''")


def transcribe_reference(audio_path: Path, language: str = "en", progress=None) -> str:
    progress = progress or (lambda message: None)
    from faster_whisper import WhisperModel

    apply_settings()
    model_name = "small.en" if language == "en" else "small"
    model = WhisperModel(model_name, device="cuda", compute_type="float16")
    progress("Whisper model ready. Transcribing reference audio...")
    segments, _ = model.transcribe(str(audio_path), language=language, vad_filter=True)
    transcript = " ".join(segment.text.strip() for segment in segments).strip()
    if not transcript:
        raise ValueError("No speech was detected in the reference audio.")
    return transcript


class ProfileWorker(QObject):
    progress = Signal(str)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(
        self, store: ProfileStore, name: str, source_audio: Path, transcript: str, language: str
    ) -> None:
        super().__init__()
        self.store = store
        self.name = name
        self.source_audio = source_audio
        self.transcript = transcript
        self.language = language

    def run(self) -> None:
        try:
            log_event("PROFILE | started")
            apply_settings()
            profile = self.store.save(
                self.name, self.source_audio, self.transcript, self.language, self.progress.emit
            )
            self.completed.emit(profile)
        except Exception:
            log_event("PROFILE | failed\n" + traceback.format_exc())
            self.failed.emit(traceback.format_exc())


class VoiceTranscriptWorker(QObject):
    progress = Signal(str)
    completed = Signal(str)
    failed = Signal(str)

    def __init__(self, audio_path: Path, language: str) -> None:
        super().__init__()
        self.audio_path = audio_path
        self.language = language

    def run(self) -> None:
        try:
            log_event(f"VOICE TRANSCRIPT | started | audio={self.audio_path}")
            apply_settings()
            transcript = transcribe_reference(
                self.audio_path, self.language, self.progress.emit
            )
            self.completed.emit(transcript)
            log_event("VOICE TRANSCRIPT | completed")
        except Exception:
            details = traceback.format_exc()
            log_event("VOICE TRANSCRIPT | failed\n" + details)
            self.failed.emit(details)


class VoiceDesignWorker(QObject):
    progress = Signal(str)
    completed = Signal(str)
    failed = Signal(str)

    def __init__(self, source: Path, destination: Path, settings: dict) -> None:
        super().__init__()
        self.source = source
        self.destination = destination
        self.settings = dict(settings)

    def run(self) -> None:
        try:
            log_event(f"VOICE DESIGN | started | source={self.source}")
            path = render_voice_design_preview(
                self.source, self.destination, self.settings, self.progress.emit
            )
            self.completed.emit(str(path))
            log_event(f"VOICE DESIGN | completed | output={path}")
        except Exception:
            details = traceback.format_exc()
            log_event("VOICE DESIGN | failed\n" + details)
            self.failed.emit(details)


class OmniVoicePreloadWorker(QObject):
    completed = Signal(str)
    failed = Signal(str)

    def __init__(self, model_name: str, device_mode: str) -> None:
        super().__init__()
        self.model_name = model_name
        self.device_mode = device_mode

    def run(self) -> None:
        try:
            log_event(f"PRELOAD | OmniVoice started | model={self.model_name} | device={self.device_mode} | HF_HOME={os.environ.get('HF_HOME', '')} | HF_HUB_DISABLE_XET={os.environ.get('HF_HUB_DISABLE_XET', '')}")
            load_cached_omnivoice(self.model_name, self.device_mode)
            self.completed.emit(f"OmniVoice ready on {self.device_mode.upper()}.")
            log_event("PRELOAD | OmniVoice completed")
        except Exception:
            details = traceback.format_exc()
            log_event("PRELOAD | OmniVoice failed\n" + details)
            self.failed.emit(details)


class PiperProfileWorker(QObject):
    progress = Signal(str)
    completed = Signal(int, list)
    failed = Signal(str)

    def __init__(self, store: ProfileStore) -> None:
        super().__init__()
        self.store = store

    def run(self) -> None:
        created = 0
        skipped: list[str] = []
        try:
            piper_exe = Path(sys.executable).parent / "Scripts" / "piper.exe"
            if not piper_exe.is_file():
                raise RuntimeError("piper-tts is not installed in the project environment.")
            models = sorted(PIPER_MODEL_DIR.glob("*.onnx"))
            for index, model_path in enumerate(models, start=1):
                config_path = Path(str(model_path) + ".json")
                if not config_path.is_file():
                    skipped.append(model_path.stem)
                    continue
                config = json.loads(config_path.read_text(encoding="utf-8"))
                language = piper_config_language(config)
                text_pool = PIPER_REFERENCE_TEXTS.get(language, PIPER_REFERENCE_TEXTS["vi"])
                self.progress.emit(f"Creating Piper clone profile {index}/{len(models)}: {model_path.stem}")
                destination = self.store.root / f"Piper - {model_path.stem}"
                destination.mkdir(parents=True, exist_ok=True)
                raw_wav = destination / ".piper-raw.wav"
                reference_wav = destination / "reference.wav"
                import soundfile as sf
                words = text_pool.split()
                word_count = min(35, len(words))
                reference_text = ""
                duration = 0.0
                for _attempt in range(6):
                    reference_text = " ".join(words[:word_count])
                    result = subprocess.run(
                        [
                            str(piper_exe), "--model", str(model_path), "--config", str(config_path),
                            "--output-file", str(raw_wav),
                        ],
                        input=reference_text,
                        text=True,
                        encoding="utf-8",
                        capture_output=True,
                        creationflags=0x08000000,
                    )
                    if result.returncode != 0 or not raw_wav.is_file():
                        break
                    duration = sf.info(raw_wav).duration
                    if 9 <= duration <= 11:
                        break
                    target_count = round(word_count * 9.8 / max(duration, 0.1))
                    word_count = max(8, min(len(words), target_count))
                if result.returncode != 0 or not raw_wav.is_file() or not 9 <= duration <= 11:
                    raw_wav.unlink(missing_ok=True)
                    skipped.append(model_path.stem)
                    self.progress.emit(
                        f"Skipped {model_path.stem}: could not fit complete speech into 9-11 seconds."
                    )
                    continue
                ffmpeg_result = subprocess.run(
                    [
                        ffmpeg_executable(), "-y", "-i", str(raw_wav), "-af",
                        "highpass=f=70,lowpass=f=11000,loudnorm=I=-20:TP=-2:LRA=7",
                        "-ac", "1", "-ar", "24000", str(reference_wav),
                    ],
                    capture_output=True, text=True, creationflags=0x08000000,
                )
                raw_wav.unlink(missing_ok=True)
                if ffmpeg_result.returncode != 0:
                    skipped.append(model_path.stem)
                    continue
                profile = {
                    "name": f"Piper - {model_path.stem}",
                    "reference_audio": str(reference_wav),
                    "reference_text": reference_text,
                    "language": "en" if language == "en" else "vi",
                    "source_model": str(model_path),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                (destination / "profile.json").write_text(
                    json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                created += 1
            self.completed.emit(created, skipped)
        except Exception:
            self.failed.emit(traceback.format_exc())


class RenderWorker(QObject):
    progress = Signal(int, int, str)
    segment_status = Signal(int, str)
    completed = Signal(str)
    cancelled = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        profile: dict,
        input_path: Path,
        output_dir: Path,
        model_name: str,
        steps: int,
        fit_timeline: bool,
        output_format: str,
        segment_limit: int | None = None,
        device_mode: str = "cuda",
        cooldown_seconds: int = 0,
        reload_every: int = 40,
        start_position: int = 1,
        end_position: int | None = None,
        overwrite: bool = False,
        normalize_audio: bool = True,
        language: str | None = None,
        speaking_style: str = "",
        auto_style: bool = False,
        style_overrides: dict[int, str] | None = None,
        output_suffix: str = "",
    ) -> None:
        super().__init__()
        self.profile = profile
        self.input_path = input_path
        self.output_dir = output_dir
        self.model_name = model_name
        self.steps = steps
        self.fit_timeline = fit_timeline
        self.output_format = output_format
        self.segment_limit = segment_limit
        self.device_mode = device_mode
        self.cooldown_seconds = cooldown_seconds
        self.reload_every = reload_every
        self.start_position = start_position
        self.end_position = end_position
        self.overwrite = overwrite
        self.normalize_audio = normalize_audio
        self.language = language
        self.speaking_style = speaking_style
        self.auto_style = auto_style
        self.style_overrides = style_overrides or {}
        self.output_suffix = output_suffix
        self.cancel_event = threading.Event()

    def request_cancel(self) -> None:
        self.cancel_event.set()
        log_event("RENDER | cancellation requested")

    def run(self) -> None:
        model = None
        voice_clone_prompt = None
        torch = None
        manifest: list[dict] = []
        generated_files: list[Path] = []
        current_position = 0
        try:
            log_event(
                f"RENDER | started | engine=omnivoice | device={self.device_mode} | "
                f"model={self.model_name}"
            )
            log_event("GPU | before torch import | " + gpu_snapshot())
            if self.device_mode == "cuda":
                os.environ.setdefault(
                    "PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True,max_split_size_mb:128"
                )
            import soundfile as sf
            import torch
            configure_ffmpeg()
            apply_settings()
            gc.collect()
            if self.device_mode == "cuda":
                torch.cuda.empty_cache()
                log_event("GPU | cache cleared before model load | " + gpu_snapshot())
            segments = parse_input(self.input_path)
            if self.segment_limit:
                segments = segments[: self.segment_limit]
            end_position = min(self.end_position or len(segments), len(segments))
            self.output_dir.mkdir(parents=True, exist_ok=True)
            dtype = torch.float16 if self.device_mode == "cuda" else torch.float32
            device_map = "cuda:0" if self.device_mode == "cuda" else "cpu"
            log_event(f"RENDER | loading OmniVoice | device_map={device_map} | dtype={dtype}")
            model = load_cached_omnivoice(
                self.model_name,
                self.device_mode,
                wait_progress=lambda message: self.progress.emit(max(1, current_position), len(segments), message),
            )
            voice_clone_prompt = model.create_voice_clone_prompt(
                self.profile["reference_audio"],
                self.profile.get("reference_text") or None,
            )
            sample_rate = 24000
            log_event("RENDER | model and reusable voice prompt loaded | " + gpu_snapshot())
            width = max(3, len(str(len(segments))))
            for position, segment in enumerate(segments, start=1):
                if position < self.start_position or position > end_position:
                    continue
                current_position = position
                if self.cancel_event.is_set():
                    self.finish_cancelled(manifest)
                    return
                stem = f"{position:0{width}d}"
                filename = f"{stem}{self.output_suffix}.{self.output_format}"
                destination = self.output_dir / filename
                if not self.overwrite and destination.is_file() and destination.stat().st_size > 0:
                    record = asdict(segment)
                    record["file"] = filename
                    manifest.append(record)
                    self.progress.emit(position, len(segments), f"Skipping completed {filename}")
                    self.segment_status.emit(position, "Completed")
                    log_event(f"RENDER | segment {position}/{len(segments)} | already completed")
                    continue
                log_event(f"RENDER | segment {position}/{len(segments)} | begin")
                self.progress.emit(position, len(segments), segment.text)
                with torch.inference_mode():
                    kwargs = {
                        "text": segment.text,
                        "voice_clone_prompt": voice_clone_prompt,
                        "num_step": self.steps,
                    }
                    if self.fit_timeline and segment.duration:
                        kwargs["duration"] = segment.duration
                    if self.language:
                        kwargs["language"] = self.language
                    direction = self.style_overrides.get(position, "").strip()
                    if not direction:
                        direction = (
                            infer_speaking_direction(segment.text, self.speaking_style)
                            if self.auto_style
                            else normalize_omnivoice_instruct(self.speaking_style)
                        )
                    else:
                        direction = normalize_omnivoice_instruct(direction)
                    if direction:
                        kwargs["instruct"] = direction
                    audio = model.generate(**kwargs)
                    audio_data = audio[0]
                log_event(f"RENDER | segment {position}/{len(segments)} | generated")
                if self.cancel_event.is_set():
                    self.finish_cancelled(manifest)
                    return
                if self.output_format == "wav":
                    sf.write(destination, audio_data, sample_rate)
                else:
                    temporary_wav = self.output_dir / f".{stem}{self.output_suffix}.wav"
                    sf.write(temporary_wav, audio_data, sample_rate)
                    result = subprocess.run(
                        [
                            ffmpeg_executable(),
                            "-y",
                            "-i",
                            str(temporary_wav),
                            "-codec:a",
                            "libmp3lame",
                            "-b:a",
                            "192k",
                            str(self.output_dir / filename),
                        ],
                        capture_output=True,
                        text=True,
                        creationflags=0x08000000,
                    )
                    temporary_wav.unlink(missing_ok=True)
                    if result.returncode != 0:
                        raise RuntimeError(f"MP3 conversion failed:\n{result.stderr[-1000:]}")
                record = asdict(segment)
                record["file"] = filename
                manifest.append(record)
                generated_files.append(destination)
                self.write_manifest(manifest, partial=True)
                self.segment_status.emit(position, "Completed")
                del audio, audio_data
                log_event(f"GPU | after segment {position}/{len(segments)} | " + gpu_snapshot())
                if (
                    self.reload_every
                    and position < len(segments)
                    and position % self.reload_every == 0
                ):
                    self.progress.emit(
                        position,
                        len(segments),
                        f"Reloading model after {position} segments to reset CUDA memory...",
                    )
                    log_event(f"RENDER | periodic model reload after segment {position}")
                    voice_clone_prompt = None
                    model = None
                    clear_cached_omnivoice(self.model_name, self.device_mode)
                    gc.collect()
                    if self.device_mode == "cuda":
                        torch.cuda.empty_cache()
                    model = load_cached_omnivoice(
                        self.model_name,
                        self.device_mode,
                        wait_progress=lambda message: self.progress.emit(position, len(segments), message),
                    )
                    voice_clone_prompt = model.create_voice_clone_prompt(
                        self.profile["reference_audio"],
                        self.profile.get("reference_text") or None,
                    )
                    log_event("RENDER | periodic model reload completed | " + gpu_snapshot())
                if self.cooldown_seconds and position < len(segments):
                    self.progress.emit(
                        position,
                        len(segments),
                        f"Cooling down for {self.cooldown_seconds} second(s)...",
                    )
                    if self.cancel_event.wait(self.cooldown_seconds):
                        self.finish_cancelled(manifest)
                        return

            numbered = [
                self.output_dir / f"{position:0{width}d}{self.output_suffix}.{self.output_format}"
                for position in range(1, len(segments) + 1)
            ]
            if self.normalize_audio and all(path.is_file() for path in numbered):
                self.progress.emit(
                    len(segments), len(segments), "Rendering complete. Normalizing completed batch..."
                )
                log_event(f"RENDER | batch normalization started | files={len(numbered)}")
                normalize_completed_batch(
                    numbered,
                    progress=lambda message: self.progress.emit(len(segments), len(segments), message),
                    cancelled=self.cancel_event.is_set,
                    originals_dir=self.output_dir / "_original_omnivoice",
                    original_files=generated_files,
                    report_path=self.output_dir / "loudness_before_after.csv",
                )
                log_event("RENDER | batch normalization completed")
            elif self.normalize_audio:
                log_event("RENDER | batch normalization skipped because the session is incomplete")
            self.write_manifest(manifest)
            (self.output_dir / "manifest.partial.json").unlink(missing_ok=True)
            self.progress.emit(len(segments), len(segments), "Done")
            log_event(f"RENDER | completed | output={self.output_dir}")
            self.completed.emit(str(self.output_dir))
        except InterruptedError:
            self.finish_cancelled(manifest)
        except Exception:
            self.write_manifest(manifest, partial=True)
            details = traceback.format_exc()
            if self.device_mode == "cuda" and "CUDA" in details:
                details += (
                    f"\nCompleted files through the last successful segment were kept. "
                    f"Restart the app, then click Render again to resume from segment "
                    f"{current_position} without regenerating earlier files."
                )
            log_event("RENDER | failed\n" + details)
            self.failed.emit(details)
        finally:
            voice_clone_prompt = None
            model = None
            gc.collect()
            if torch is not None and self.device_mode == "cuda":
                try:
                    torch.cuda.empty_cache()
                    log_event("GPU | cache cleared after render | " + gpu_snapshot())
                except Exception:
                    log_event("GPU | cleanup failed\n" + traceback.format_exc())

    def finish_cancelled(self, manifest: list[dict]) -> None:
        self.write_manifest(manifest, partial=True)
        message = f"Stopped safely. Kept {len(manifest)} completed audio file(s) in {self.output_dir}"
        log_event("RENDER | " + message)
        self.cancelled.emit(message)

    def write_manifest(self, manifest: list[dict], partial: bool = False) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        name = "manifest.partial.json" if partial else "manifest.json"
        (self.output_dir / name).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def install_moss_torchaudio_load_fallback(torch_module, soundfile_module):
    """Make torchaudio.load work without TorchCodec for MOSS reference files."""
    import numpy as np
    import torchaudio

    original_load = torchaudio.load

    def load_audio(
        uri, frame_offset: int = 0, num_frames: int = -1,
        normalize: bool = True, channels_first: bool = True,
        format=None, buffer_size: int = 4096, backend=None,
    ):
        path = Path(os.fspath(uri))
        if not path.is_file():
            return original_load(
                uri, frame_offset=frame_offset, num_frames=num_frames,
                normalize=normalize, channels_first=channels_first,
                format=format, buffer_size=buffer_size, backend=backend,
            )
        frames = int(num_frames) if num_frames is not None and int(num_frames) >= 0 else -1
        audio, sample_rate = soundfile_module.read(
            path, start=max(0, int(frame_offset)), frames=frames,
            dtype="float32", always_2d=True,
        )
        audio = np.ascontiguousarray(audio.T if channels_first else audio)
        return torch_module.from_numpy(audio), int(sample_rate)

    torchaudio.load = load_audio
    return torchaudio, original_load


class MossTTSWorker(QObject):
    """Local Transformers inference worker for MOSS-TTS v1.5."""

    progress = Signal(int, int, str)
    timing = Signal(int, int, float, float)
    segment_status = Signal(int, str)
    completed = Signal(str)
    cancelled = Signal(str)
    failed = Signal(str)

    LANGUAGE_NAMES = {
        "zh": "Chinese", "yue": "Cantonese", "en": "English", "ar": "Arabic",
        "cs": "Czech", "da": "Danish", "nl": "Dutch", "fi": "Finnish",
        "fr": "French", "de": "German", "el": "Greek", "he": "Hebrew",
        "hi": "Hindi", "hu": "Hungarian", "it": "Italian", "ja": "Japanese",
        "ko": "Korean", "mk": "Macedonian", "ms": "Malay", "fa": "Persian",
        "pl": "Polish", "pt": "Portuguese", "ro": "Romanian", "ru": "Russian",
        "es": "Spanish", "sw": "Swahili", "sv": "Swedish", "tl": "Tagalog",
        "th": "Thai", "tr": "Turkish", "vi": "Vietnamese",
    }

    def __init__(
        self, profile: dict, input_path: Path, output_dir: Path, model_name: str,
        device_mode: str, dtype_name: str, attention: str, language: str,
        max_new_tokens: int, output_format: str, segment_limit: int | None = None,
        cooldown_seconds: int = 0, start_position: int = 1,
        end_position: int | None = None, overwrite: bool = False,
        normalize_audio: bool = False,
        auto_duration: bool = True,
        keep_model_loaded: bool = False,
    ) -> None:
        super().__init__()
        self.profile = profile
        self.input_path = input_path
        self.output_dir = output_dir
        self.model_name = model_name
        self.device_mode = device_mode
        self.dtype_name = dtype_name
        self.attention = attention
        self.language = language
        self.max_new_tokens = max_new_tokens
        self.output_format = output_format
        self.segment_limit = segment_limit
        self.cooldown_seconds = cooldown_seconds
        self.start_position = start_position
        self.end_position = end_position
        self.overwrite = overwrite
        self.normalize_audio = normalize_audio
        self.auto_duration = auto_duration
        self.keep_model_loaded = keep_model_loaded
        self.cancel_event = threading.Event()

    def request_cancel(self) -> None:
        self.cancel_event.set()
        log_event("MOSS-TTS | cancellation requested")

    def run(self) -> None:
        global _MOSS_RUNTIME_CACHE
        model = processor = torch = None
        torchaudio_module = original_torchaudio_load = None
        completed_successfully = False
        manifest: list[dict] = []
        generated_files: list[Path] = []
        run_started_at = time.monotonic()
        try:
            import importlib.util
            import numpy as np
            import soundfile as sf
            import torch as torch_module
            from huggingface_hub import snapshot_download
            from transformers import AutoModel, AutoProcessor

            torch = torch_module
            torchaudio_module, original_torchaudio_load = install_moss_torchaudio_load_fallback(
                torch, sf
            )
            if self.device_mode == "cuda" and not torch.cuda.is_available():
                raise RuntimeError("CUDA was selected, but PyTorch cannot find a CUDA GPU.")
            device = "cuda" if self.device_mode == "cuda" else "cpu"
            dtype = torch.float32
            if device == "cuda":
                dtype = torch.float16 if self.dtype_name == "float16" else torch.bfloat16
            attention = self.attention
            if attention == "auto":
                flash_ok = (
                    device == "cuda" and importlib.util.find_spec("flash_attn") is not None
                    and torch.cuda.get_device_capability()[0] >= 8
                )
                attention = "flash_attention_2" if flash_ok else ("sdpa" if device == "cuda" else "eager")
            torch.backends.cuda.enable_cudnn_sdp(False)
            torch.backends.cuda.enable_flash_sdp(True)
            torch.backends.cuda.enable_mem_efficient_sdp(True)
            torch.backends.cuda.enable_math_sdp(True)

            segments = parse_input(self.input_path)
            if self.segment_limit:
                segments = segments[:self.segment_limit]
            total_source = len(parse_input(self.input_path))
            end = min(self.end_position or total_source, len(segments))
            selected = [
                (position, segments[position - 1])
                for position in range(self.start_position, end + 1)
            ]
            if not selected:
                raise ValueError("The selected render range does not contain any segments.")
            reference_audio = Path(self.profile.get("reference_audio", ""))
            if not reference_audio.is_file():
                raise ValueError("The selected voice profile reference audio is missing.")

            self.output_dir.mkdir(parents=True, exist_ok=True)
            raw_model_source = self.model_name.strip().strip('"').strip("'")
            local_model_path = Path(raw_model_source)
            if local_model_path.is_dir():
                model_source = str(local_model_path.resolve())
                canonical_model_name = model_source
            else:
                canonical_model_name = raw_model_source.replace("\\", "/").strip("/")
                if re.match(r"^[A-Za-z]:/", canonical_model_name):
                    raise ValueError(f"Local MOSS-TTS model folder does not exist: {raw_model_source}")
                self.progress.emit(
                    0, len(selected),
                    f"Resolving Hugging Face snapshot {canonical_model_name}...",
                )
                # MOSS-TTS's custom processor converts repo IDs to pathlib.Path. On Windows
                # that changes '/' to '\\' and Hugging Face rejects the resulting repo ID.
                # Resolve the snapshot first, then give the processor a real local directory.
                model_source = snapshot_download(repo_id=canonical_model_name)
            cache_key = (canonical_model_name, device, str(dtype), attention)
            cached_key = _MOSS_RUNTIME_CACHE.get("key")
            using_cache = cached_key == cache_key
            self.progress.emit(
                0, len(selected),
                ("Reusing loaded MOSS-TTS model..." if using_cache else
                 f"Loading {self.model_name} ({attention}, {device})..."),
            )
            log_event(
                f"MOSS-TTS | load | model={self.model_name} | device={device} | "
                f"dtype={dtype} | attention={attention}"
            )
            if using_cache:
                processor = _MOSS_RUNTIME_CACHE["processor"]
                model = _MOSS_RUNTIME_CACHE["model"]
            else:
                _MOSS_RUNTIME_CACHE.clear()
                processor = AutoProcessor.from_pretrained(model_source, trust_remote_code=True)
                processor.audio_tokenizer = processor.audio_tokenizer.to(device)
                model = AutoModel.from_pretrained(
                    model_source, trust_remote_code=True,
                    attn_implementation=attention, torch_dtype=dtype,
                ).to(device)
                model.eval()
                _MOSS_RUNTIME_CACHE.update(
                    {"key": cache_key, "processor": processor, "model": model}
                )
            sample_rate = int(processor.model_config.sampling_rate)
            width = max(3, len(str(total_source)))
            language_name = self.LANGUAGE_NAMES.get(self.language)

            with torch.no_grad():
                for completed_count, (position, segment) in enumerate(selected, start=1):
                    if self.cancel_event.is_set():
                        self.cancelled.emit(
                            f"Stopped safely. Kept {len(manifest)} completed audio file(s)."
                        )
                        return
                    stem = f"{position:0{width}d}"
                    destination = self.output_dir / f"{stem}.{self.output_format}"
                    if destination.is_file() and not self.overwrite:
                        self.segment_status.emit(position, "Skipped")
                        self.progress.emit(completed_count, len(selected), f"Skipped existing {destination.name}")
                        self.timing.emit(
                            completed_count, len(selected),
                            time.monotonic() - run_started_at, 0.0,
                        )
                        continue
                    self.segment_status.emit(position, "Rendering")
                    self.progress.emit(completed_count - 1, len(selected), f"Generating segment {position}...")
                    segment_started_at = time.monotonic()
                    message_kwargs = {
                        "text": segment.text,
                        "reference": [str(reference_audio.resolve())],
                    }
                    if language_name:
                        message_kwargs["language"] = language_name
                    expected_tokens = None
                    if self.auto_duration:
                        expected_tokens = max(
                            10, min(self.max_new_tokens, round(moss_expected_duration(segment.text) * 12.5))
                        )
                        message_kwargs["tokens"] = expected_tokens
                    try:
                        user_message = processor.build_user_message(**message_kwargs)
                    except TypeError:
                        # Local Transformer v1.0 predates v1.5's explicit language field.
                        # It still supports English and the other original languages by text.
                        if "language" not in message_kwargs:
                            raise
                        message_kwargs.pop("language")
                        user_message = processor.build_user_message(**message_kwargs)
                    conversation = [[user_message]]
                    batch = processor(conversation, mode="generation")
                    generation_limit = self.max_new_tokens
                    if expected_tokens is not None:
                        generation_limit = min(
                            self.max_new_tokens, max(expected_tokens + 8, round(expected_tokens * 1.35))
                        )
                    generation_kwargs = dict(
                        input_ids=batch["input_ids"].to(device),
                        attention_mask=batch["attention_mask"].to(device),
                        max_new_tokens=generation_limit,
                    )
                    if "local-transformer" in canonical_model_name.lower() and sample_rate >= 48000:
                        generation_kwargs.update(
                            do_sample=True,
                            audio_temperature=1.7,
                            audio_top_p=0.8,
                            audio_top_k=25,
                            audio_repetition_penalty=1.0,
                        )
                    elif "local-transformer" in canonical_model_name.lower():
                        generation_kwargs.update(
                            do_sample=True,
                            audio_temperature=1.0,
                            audio_top_p=0.95,
                            audio_top_k=50,
                            audio_repetition_penalty=1.1,
                        )
                    outputs = model.generate(**generation_kwargs)
                    decoded = processor.decode(outputs)
                    if not decoded or not decoded[0].audio_codes_list:
                        raise RuntimeError(f"MOSS-TTS returned no audio for segment {position}.")
                    audio = decoded[0].audio_codes_list[0].detach().float().cpu().numpy()
                    audio = np.asarray(audio).squeeze()
                    # Local Transformer v1.5 decodes stereo as [channels, samples],
                    # while soundfile expects [samples, channels]. Delay is mono [samples].
                    if audio.ndim == 2 and audio.shape[0] <= 8 and audio.shape[1] > audio.shape[0]:
                        audio = audio.T
                    wav_path = destination if self.output_format == "wav" else self.output_dir / f".{stem}.wav"
                    sf.write(wav_path, audio, sample_rate)
                    if self.output_format == "mp3":
                        result = subprocess.run(
                            [ffmpeg_executable(), "-y", "-i", str(wav_path), "-codec:a", "libmp3lame",
                             "-b:a", "192k", str(destination)],
                            capture_output=True, text=True, creationflags=0x08000000,
                        )
                        wav_path.unlink(missing_ok=True)
                        if result.returncode != 0:
                            raise RuntimeError(f"MP3 conversion failed:\n{result.stderr[-1000:]}")
                    record = asdict(segment)
                    record["file"] = destination.name
                    record["engine"] = "MOSS-TTS-v1.5"
                    manifest.append(record)
                    generated_files.append(destination)
                    (self.output_dir / "manifest.partial.json").write_text(
                        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
                    )
                    self.segment_status.emit(position, "Completed")
                    self.progress.emit(completed_count, len(selected), f"Completed {destination.name}")
                    self.timing.emit(
                        completed_count, len(selected),
                        time.monotonic() - run_started_at,
                        time.monotonic() - segment_started_at,
                    )
                    del batch, outputs, decoded, audio
                    if self.cooldown_seconds and completed_count < len(selected):
                        if self.cancel_event.wait(self.cooldown_seconds):
                            self.cancelled.emit(
                                f"Stopped safely. Kept {len(manifest)} completed audio file(s)."
                            )
                            return

            numbered = [
                self.output_dir / f"{position:0{width}d}.{self.output_format}"
                for position in range(1, total_source + 1)
            ]
            if self.normalize_audio and all(path.is_file() for path in numbered):
                normalize_completed_batch(
                    numbered,
                    progress=lambda message: self.progress.emit(len(selected), len(selected), message),
                    originals_dir=self.output_dir / "_original_moss_tts",
                    original_files=generated_files,
                    report_path=self.output_dir / "loudness_before_after.csv",
                )
            (self.output_dir / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            (self.output_dir / "manifest.partial.json").unlink(missing_ok=True)
            completed_successfully = True
            self.completed.emit(str(self.output_dir))
        except ModuleNotFoundError as exc:
            self.failed.emit(
                "MOSS-TTS local runtime is not installed. Install the official OpenMOSS/MOSS-TTS "
                "package in this environment (Transformers 5.x is required).\n\n" + str(exc)
            )
        except Exception:
            details = traceback.format_exc()
            log_event("MOSS-TTS | failed\n" + details)
            self.failed.emit(details)


class MossPreloadWorker(QObject):
    completed = Signal(str)
    failed = Signal(str)

    def __init__(self, model_name: str, device_mode: str, dtype_name: str, attention: str) -> None:
        super().__init__()
        self.model_name = model_name
        self.device_mode = device_mode
        self.dtype_name = dtype_name
        self.attention = attention

    def run(self) -> None:
        global _MOSS_RUNTIME_CACHE
        try:
            import importlib.util
            import torch
            from huggingface_hub import snapshot_download
            from transformers import AutoModel, AutoProcessor

            if self.device_mode == "cuda" and not torch.cuda.is_available():
                raise RuntimeError("CUDA was selected, but PyTorch cannot find a CUDA GPU.")
            device = "cuda" if self.device_mode == "cuda" else "cpu"
            dtype = torch.float32
            if device == "cuda":
                dtype = torch.float16 if self.dtype_name == "float16" else torch.bfloat16
            attention = self.attention
            if attention == "auto":
                flash_ok = (
                    device == "cuda" and importlib.util.find_spec("flash_attn") is not None
                    and torch.cuda.get_device_capability()[0] >= 8
                )
                attention = "flash_attention_2" if flash_ok else ("sdpa" if device == "cuda" else "eager")
            raw_source = self.model_name.strip().strip('"').strip("'")
            local_path = Path(raw_source)
            if local_path.is_dir():
                model_source = str(local_path.resolve())
                canonical_name = model_source
            else:
                canonical_name = raw_source.replace("\\", "/").strip("/")
                model_source = snapshot_download(repo_id=canonical_name)
            cache_key = (canonical_name, device, str(dtype), attention)
            if _MOSS_RUNTIME_CACHE.get("key") != cache_key:
                _MOSS_RUNTIME_CACHE.clear()
                processor = AutoProcessor.from_pretrained(model_source, trust_remote_code=True)
                processor.audio_tokenizer = processor.audio_tokenizer.to(device)
                model = AutoModel.from_pretrained(
                    model_source, trust_remote_code=True,
                    attn_implementation=attention, torch_dtype=dtype,
                ).to(device)
                model.eval()
                _MOSS_RUNTIME_CACHE.update(
                    {"key": cache_key, "processor": processor, "model": model}
                )
            message = (
                f"MOSS-TTS ready · {device.upper()} · {str(dtype).removeprefix('torch.')} · "
                f"{attention}"
            )
            log_event("PRELOAD | " + message)
            self.completed.emit(message)
        except Exception:
            _MOSS_RUNTIME_CACHE.clear()
            details = traceback.format_exc()
            log_event("PRELOAD | MOSS-TTS failed\n" + details)
            self.failed.emit(details)


class MossAudioCheckWorker(QObject):
    progress = Signal(int, int, str)
    segment_status = Signal(int, str)
    review_detected = Signal(int, str)
    completed = Signal(str)
    failed = Signal(str)
    cancelled = Signal(str)

    def __init__(
        self, jobs: list[tuple[int, str, Path]], output_dir: Path, language: str,
        worker_count: int = 4,
    ) -> None:
        super().__init__()
        self.jobs = jobs
        self.output_dir = output_dir
        self.language = language
        self.worker_count = max(1, min(8, int(worker_count)))
        self.cancel_event = threading.Event()
        self.review_positions: list[int] = []
        self.review_reasons: dict[int, str] = {}

    def request_cancel(self) -> None:
        self.cancel_event.set()

    def run(self) -> None:
        try:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            import soundfile as sf
            from faster_whisper import WhisperModel

            rows: list[dict[str, object]] = []
            review_count = 0
            total = len(self.jobs)
            completed = 0
            asr_jobs: list[tuple[int, str, Path, float, float, bool]] = []

            def record_result(row: dict[str, object], reasons: list[str]) -> None:
                nonlocal completed, review_count
                position = int(row["segment"])
                status = "Needs review" if reasons else "Verified"
                row["status"] = status
                if reasons:
                    review_count += 1
                    self.review_positions.append(position)
                    self.review_reasons[position] = "; ".join(reasons)
                self.segment_status.emit(position, status)
                if reasons:
                    self.review_detected.emit(position, "; ".join(reasons))
                rows.append(row)
                completed += 1
                self.progress.emit(
                    completed, total,
                    f"Parallel ASR {completed}/{total} · {review_count} need review",
                )

            # Duration scanning is cheap and immediately catches runaway generations.
            for position, expected_text, audio_path in self.jobs:
                if self.cancel_event.is_set():
                    self.cancelled.emit(f"Audio check stopped after {completed}/{total} files.")
                    return
                info = sf.info(str(audio_path))
                duration = float(info.duration)
                expected_duration = moss_expected_duration(expected_text)
                too_long = duration > max(8.0, expected_duration * 3.0)
                too_short = duration < max(0.25, expected_duration * 0.28)
                if too_long:
                    reasons = [
                        f"duration {duration:.1f}s vs expected ~{expected_duration:.1f}s"
                    ]
                    record_result(
                        {
                            "segment": position,
                            "status": "",
                            "duration_seconds": f"{duration:.3f}",
                            "expected_seconds": f"{expected_duration:.3f}",
                            "text_match": "0.000",
                            "expected_text": expected_text,
                            "asr_transcript": "[ASR skipped: obvious duration runaway]",
                            "reason": "; ".join(reasons),
                            "audio_file": str(audio_path),
                        },
                        reasons,
                    )
                else:
                    asr_jobs.append(
                        (position, expected_text, audio_path, duration, expected_duration, too_short)
                    )

            if asr_jobs and not self.cancel_event.is_set():
                self.progress.emit(
                    completed, total,
                    f"Loading CPU ASR · {self.worker_count} parallel workers...",
                )
                cpu_threads = max(1, (os.cpu_count() or self.worker_count) // self.worker_count)
                asr_model = WhisperModel(
                    cached_hf_snapshot("Systran/faster-whisper-small.en"),
                    device="cpu",
                    compute_type="int8",
                    cpu_threads=cpu_threads,
                    num_workers=self.worker_count,
                )

                def transcribe_one(job):
                    position, expected_text, audio_path, duration, expected_duration, too_short = job
                    segments, _info = asr_model.transcribe(
                        str(audio_path),
                        language=self.language if self.language == "en" else None,
                        vad_filter=True,
                        beam_size=3,
                    )
                    transcript = " ".join(segment.text.strip() for segment in segments).strip()
                    similarity = difflib.SequenceMatcher(
                        None,
                        normalized_speech_text(expected_text),
                        normalized_speech_text(transcript),
                    ).ratio()
                    reasons: list[str] = []
                    if too_short:
                        reasons.append(
                            f"duration {duration:.1f}s vs expected ~{expected_duration:.1f}s"
                        )
                    if similarity < 0.58:
                        reasons.append(f"ASR text match only {similarity:.0%}")
                    return {
                        "segment": position,
                        "status": "",
                        "duration_seconds": f"{duration:.3f}",
                        "expected_seconds": f"{expected_duration:.3f}",
                        "text_match": f"{similarity:.3f}",
                        "expected_text": expected_text,
                        "asr_transcript": transcript,
                        "reason": "; ".join(reasons),
                        "audio_file": str(audio_path),
                    }, reasons

                with ThreadPoolExecutor(
                    max_workers=self.worker_count, thread_name_prefix="moss-asr"
                ) as pool:
                    futures = [pool.submit(transcribe_one, job) for job in asr_jobs]
                    for future in as_completed(futures):
                        if self.cancel_event.is_set():
                            for pending in futures:
                                pending.cancel()
                            self.cancelled.emit(
                                f"Audio check stopped after {completed}/{total} files."
                            )
                            return
                        row, reasons = future.result()
                        record_result(row, reasons)
            report_path = self.output_dir / "moss_audio_check.csv"
            merged_rows: dict[int, dict[str, object]] = {}
            if report_path.is_file():
                try:
                    with report_path.open("r", newline="", encoding="utf-8-sig") as handle:
                        for previous in csv.DictReader(handle):
                            merged_rows[int(previous["segment"])] = dict(previous)
                except (OSError, ValueError, KeyError):
                    merged_rows = {}
            for row in rows:
                merged_rows[int(row["segment"])] = row
            report_rows = [merged_rows[key] for key in sorted(merged_rows)]
            # CSV viewers can keep this file locked on Windows. QA and automatic
            # repair must continue even while the user is viewing an older report.
            temp_report = report_path.with_name(
                f".{report_path.stem}.{os.getpid()}.{threading.get_ident()}.tmp"
            )
            with temp_report.open("w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(report_rows[0].keys()))
                writer.writeheader()
                writer.writerows(report_rows)
            saved_report = report_path
            report_note = ""
            try:
                os.replace(temp_report, report_path)
            except PermissionError:
                saved_report = report_path.with_name(
                    f"moss_audio_check_{datetime.now():%Y%m%d_%H%M%S}.csv"
                )
                os.replace(temp_report, saved_report)
                report_note = " (main report was open; saved a new report instead)"
            self.completed.emit(
                f"Audio check complete: {review_count}/{total} file(s) need review. "
                f"Report: {saved_report}{report_note}"
            )
        except Exception:
            self.failed.emit(traceback.format_exc())


class NormalizeBatchWorker(QObject):
    progress = Signal(str)
    completed = Signal(str)
    failed = Signal(str)

    def __init__(
        self, source_dir: Path, output_format: str, output_suffix: str = "",
        originals_dir_name: str = "_original_omnivoice",
    ) -> None:
        super().__init__()
        self.source_dir = source_dir
        self.output_format = output_format
        self.output_suffix = output_suffix
        self.originals_dir_name = originals_dir_name

    def run(self) -> None:
        try:
            configure_ffmpeg()
            numbered = re.compile(
                rf"^\d+{re.escape(self.output_suffix)}\.{re.escape(self.output_format)}$",
                re.IGNORECASE,
            )
            files = sorted(
                (path for path in self.source_dir.iterdir() if numbered.match(path.name)),
                key=lambda path: int(path.stem.removesuffix(self.output_suffix)),
            )
            if not files:
                raise ValueError(
                    f"No numbered {self.output_format.upper()} files were found in "
                    f"{self.source_dir}."
                )
            log_event(f"NORMALIZE RETRY | started | source={self.source_dir} | files={len(files)}")
            normalize_completed_batch(
                files,
                progress=self.progress.emit,
                originals_dir=self.source_dir / self.originals_dir_name,
                original_files=[],
                report_path=self.source_dir / "loudness_before_after.csv",
            )
            log_event("NORMALIZE RETRY | completed")
            self.completed.emit(str(self.source_dir))
        except Exception:
            details = traceback.format_exc()
            log_event("NORMALIZE RETRY | failed\n" + details)
            self.failed.emit(details)


class MergeWorker(QObject):
    progress = Signal(str)
    completed = Signal(str)
    failed = Signal(str)

    def __init__(
        self, source_dir: Path, output_format: str, pause_seconds: float, output_suffix: str = ""
    ) -> None:
        super().__init__()
        self.source_dir = source_dir
        self.output_format = output_format
        self.pause_seconds = pause_seconds
        self.output_suffix = output_suffix

    def run(self) -> None:
        try:
            log_event(f"MERGE | started | source={self.source_dir}")
            numbered = re.compile(
                rf"^\d+{re.escape(self.output_suffix)}\.(wav|mp3)$", re.IGNORECASE
            )
            files = sorted(
                (path for path in self.source_dir.iterdir() if numbered.match(path.name)),
                key=lambda path: int(path.stem.removesuffix(self.output_suffix)),
            )
            if not files:
                raise ValueError("No numbered WAV/MP3 segment files were found in the output folder.")

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            destination = self.source_dir.parent / (
                f"{self.source_dir.name}{self.output_suffix}_merged_{timestamp}.{self.output_format}"
            )
            self.progress.emit(f"Merging {len(files)} segments into {destination.name}...")
            codec = ["-codec:a", "pcm_s16le"] if self.output_format == "wav" else [
                "-codec:a",
                "libmp3lame",
                "-b:a",
                "192k",
            ]
            with tempfile.TemporaryDirectory(prefix="voiceover-merge-", dir=self.source_dir) as temp:
                temp_dir = Path(temp)
                pause_file = temp_dir / f"pause.{self.output_format}"
                if self.pause_seconds > 0:
                    pause_codec = ["-codec:a", "pcm_s16le"] if self.output_format == "wav" else [
                        "-codec:a", "libmp3lame", "-b:a", "192k"
                    ]
                    pause_result = subprocess.run(
                        [
                            ffmpeg_executable(), "-y", "-f", "lavfi", "-i",
                            f"anullsrc=r=24000:cl=mono:d={self.pause_seconds:.3f}",
                            *pause_codec, str(pause_file),
                        ],
                        capture_output=True, text=True, creationflags=0x08000000,
                    )
                    if pause_result.returncode != 0:
                        raise RuntimeError(f"Could not create merge pause:\n{pause_result.stderr[-1000:]}")
                concat_path = temp_dir / "concat.txt"
                with concat_path.open("w", encoding="utf-8") as concat_file:
                    for index, path in enumerate(files):
                        concat_file.write(f"file '{ffmpeg_concat_path(path)}'\n")
                        if self.pause_seconds > 0 and index < len(files) - 1:
                            concat_file.write(f"file '{ffmpeg_concat_path(pause_file)}'\n")
                result = subprocess.run(
                    [
                        ffmpeg_executable(), "-y", "-f", "concat", "-safe", "0",
                        "-i", str(concat_path), *codec, str(destination),
                    ],
                    capture_output=True,
                    text=True,
                    creationflags=0x08000000,
                )
            if result.returncode != 0:
                raise RuntimeError(f"Audio merge failed:\n{result.stderr[-2000:]}")
            self.completed.emit(str(destination))
        except Exception:
            log_event("MERGE | failed\n" + traceback.format_exc())
            self.failed.emit(traceback.format_exc())


class VideoIntegrityCheckWorker(QObject):
    progress = Signal(str)
    completed = Signal(int, int)

    def __init__(self, videos: list[tuple[int, Path]]) -> None:
        super().__init__()
        self.videos = videos

    def run(self) -> None:
        failed = 0
        total = len(self.videos)
        for current, (batch_index, path) in enumerate(self.videos, start=1):
            self.progress.emit(
                f"[Batch {batch_index}] Checking video integrity {current}/{total}: {path.name}"
            )
            try:
                result = subprocess.run(
                    [
                        ffmpeg_executable(),
                        "-v", "error",
                        "-xerror",
                        "-i", str(path),
                        "-map", "0:v:0",
                        "-map", "0:a?",
                        "-f", "null",
                        "-",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=900,
                    creationflags=0x08000000 if sys.platform == "win32" else 0,
                )
                if result.returncode != 0:
                    failed += 1
                    reason = (result.stderr or "FFmpeg could not decode the video.").strip()
                    self.progress.emit(
                        f"[Batch {batch_index}] CORRUPT VIDEO: {path} | "
                        f"{reason[-600:].replace(chr(10), ' ')}"
                    )
            except Exception as exc:
                failed += 1
                self.progress.emit(
                    f"[Batch {batch_index}] CORRUPT VIDEO: {path} | {exc}"
                )
        self.completed.emit(total, failed)


class OutputVideoMergeWorker(QObject):
    progress = Signal(str)
    completed = Signal(list)
    failed = Signal(str)

    def __init__(self, jobs: list[tuple[int, Path, list[Path]]]) -> None:
        super().__init__()
        self.jobs = jobs

    def run(self) -> None:
        outputs: list[str] = []
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            for current, (batch_index, output_root, videos) in enumerate(self.jobs, start=1):
                merge_dir = output_root / f"merged_{timestamp}"
                merge_dir.mkdir(parents=True, exist_ok=True)
                concat_path = merge_dir / "concat.txt"
                merged_path = merge_dir / f"batch_{batch_index:02d}_merged.mp4"
                with concat_path.open("w", encoding="utf-8") as concat_file:
                    for video in videos:
                        concat_file.write(f"file '{ffmpeg_concat_path(video)}'\n")
                self.progress.emit(
                    f"[Batch {batch_index}] Merging {len(videos)} root video file(s) "
                    f"({current}/{len(self.jobs)})..."
                )
                result = subprocess.run(
                    [
                        ffmpeg_executable(),
                        "-y",
                        "-f", "concat",
                        "-safe", "0",
                        "-i", str(concat_path),
                        "-c", "copy",
                        "-movflags", "+faststart",
                        str(merged_path),
                    ],
                    capture_output=True,
                    text=True,
                    creationflags=0x08000000 if sys.platform == "win32" else 0,
                )
                concat_path.unlink(missing_ok=True)
                if result.returncode != 0:
                    raise RuntimeError(
                        f"[Batch {batch_index}] Video merge failed:\n{result.stderr[-2000:]}"
                    )
                outputs.append(str(merged_path))
                self.progress.emit(f"[Batch {batch_index}] Merged video: {merged_path}")
            self.completed.emit(outputs)
        except Exception:
            self.failed.emit(traceback.format_exc())


class VideoEffectMediaPreflightWorker(QObject):
    progress = Signal(str)
    completed = Signal(list)

    def __init__(self, jobs: list[dict]) -> None:
        super().__init__()
        self.jobs = jobs

    def run(self) -> None:
        from PIL import Image

        errors: list[str] = []
        for batch_index, job in enumerate(self.jobs, start=1):
            image_files = sorted(
                (
                    path
                    for path in Path(job["images"]).iterdir()
                    if path.is_file() and path.suffix.lower() in VIDEO_IMAGE_EXTS
                ),
                key=lambda path: path.name.lower(),
            )
            audio_files = sorted(
                (
                    path
                    for path in Path(job["audios"]).iterdir()
                    if path.is_file() and path.suffix.lower() in VIDEO_AUDIO_EXTS
                ),
                key=lambda path: path.name.lower(),
            )
            self.progress.emit(
                f"[Batch {batch_index}] Preflight | checking {len(image_files)} image(s) "
                f"and {len(audio_files)} audio file(s)..."
            )
            for current, path in enumerate(image_files, start=1):
                try:
                    with Image.open(path) as image:
                        image.verify()
                    with Image.open(path) as image:
                        image.load()
                except Exception as exc:
                    errors.append(f"[Batch {batch_index}] CORRUPT IMAGE: {path} | {exc}")
                if current % 25 == 0 or current == len(image_files):
                    self.progress.emit(
                        f"[Batch {batch_index}] Images checked: {current}/{len(image_files)}"
                    )
            for current, path in enumerate(audio_files, start=1):
                try:
                    result = subprocess.run(
                        [
                            ffmpeg_executable(),
                            "-v", "error",
                            "-xerror",
                            "-i", str(path),
                            "-map", "0:a:0",
                            "-f", "null",
                            "-",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=900,
                        creationflags=0x08000000 if sys.platform == "win32" else 0,
                    )
                    if result.returncode != 0:
                        reason = (result.stderr or "FFmpeg could not decode the audio.").strip()
                        errors.append(
                            f"[Batch {batch_index}] CORRUPT AUDIO: {path} | "
                            f"{reason[-600:].replace(chr(10), ' ')}"
                        )
                except Exception as exc:
                    errors.append(f"[Batch {batch_index}] CORRUPT AUDIO: {path} | {exc}")
                if current % 10 == 0 or current == len(audio_files):
                    self.progress.emit(
                        f"[Batch {batch_index}] Audios checked: {current}/{len(audio_files)}"
                    )
        self.completed.emit(errors)


class VideoEffectWorker(QObject):
    progress = Signal(str)
    segment_progress = Signal(int, int, str)
    completed = Signal(str)
    cancelled = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        script_path: Path,
        images_dir: Path,
        audios_dir: Path,
        output_dir: Path,
        width: int,
        height: int,
        fps: int,
        crf: int,
        codec: str,
        workers: int,
        pattern: str,
        random_effects: bool,
        bounce: bool,
        zoom_scale: float,
        base_crop: float,
        edge_reach: float,
        face_safe: float,
        speed: float,
        pre_silence: float,
        min_motion: float,
        combo_radius: float,
        combo_offset_x: float,
        combo_offset_y: float,
        retro_preset: str,
        retro_scratches_enabled: bool,
        retro_scratch: float,
        retro_dust_enabled: bool,
        retro_dust: float,
        retro_grain_enabled: bool,
        retro_grain: float,
        retro_flicker_enabled: bool,
        retro_flicker: float,
        retro_vignette_enabled: bool,
        retro_vignette: float,
        retro_color_fade_enabled: bool,
        retro_color_fade: float,
        retro_scan_lines_enabled: bool,
        retro_scan_lines: float,
        merge_videos: bool,
        segments_in_output_root: bool = False,
    ) -> None:
        super().__init__()
        self.script_path = script_path
        self.images_dir = images_dir
        self.audios_dir = audios_dir
        self.output_dir = output_dir
        self.width = width
        self.height = height
        self.fps = fps
        self.crf = crf
        self.codec = codec
        self.workers = workers
        self.pattern = pattern
        self.random_effects = random_effects
        self.bounce = bounce
        self.zoom_scale = zoom_scale
        self.base_crop = base_crop
        self.edge_reach = edge_reach
        self.face_safe = face_safe
        self.speed = speed
        self.pre_silence = pre_silence
        self.min_motion = min_motion
        self.combo_radius = combo_radius
        self.combo_offset_x = combo_offset_x
        self.combo_offset_y = combo_offset_y
        self.retro_preset = retro_preset
        self.retro_scratches_enabled = retro_scratches_enabled
        self.retro_scratch = retro_scratch
        self.retro_dust_enabled = retro_dust_enabled
        self.retro_dust = retro_dust
        self.retro_grain_enabled = retro_grain_enabled
        self.retro_grain = retro_grain
        self.retro_flicker_enabled = retro_flicker_enabled
        self.retro_flicker = retro_flicker
        self.retro_vignette_enabled = retro_vignette_enabled
        self.retro_vignette = retro_vignette
        self.retro_color_fade_enabled = retro_color_fade_enabled
        self.retro_color_fade = retro_color_fade
        self.retro_scan_lines_enabled = retro_scan_lines_enabled
        self.retro_scan_lines = retro_scan_lines
        self.merge_videos = merge_videos
        self.segments_in_output_root = segments_in_output_root
        self.cancel_event = threading.Event()
        self.recent_output: list[str] = []
        self.last_status_emit = 0.0

    def request_cancel(self) -> None:
        self.cancel_event.set()
        log_event("VIDEO EFFECT | cancellation requested")

    def run(self) -> None:
        started = time.monotonic()
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            codec = self.codec
            workers = self.workers
            gpu_codec = self.detect_gpu_codec()
            if codec == "auto":
                if gpu_codec:
                    codec = gpu_codec
                    suggested = max(2, min(8, (os.cpu_count() or 2) // 2 or 2))
                    workers = max(workers, suggested)
                    self.progress.emit(
                        f"[GPU] Using {gpu_codec}; rendering up to {workers} segment(s) in parallel."
                    )
                else:
                    suggested = max(2, min(4, (os.cpu_count() or 2) // 2 or 2))
                    workers = max(workers, suggested)
                    self.progress.emit(
                        f"[CPU] No GPU encoder detected; using libx264 fallback with {workers} worker(s)."
                    )
            elif codec != "libx264":
                if self.test_video_encoder(codec):
                    self.progress.emit(
                        f"[GPU] Using selected encoder {codec}; rendering up to {workers} segment(s) in parallel."
                    )
                else:
                    self.progress.emit(
                        f"[GPU] Selected encoder {codec} is not usable; FFmpeg may fail unless codec is changed."
                    )
            else:
                self.progress.emit(f"[CPU] Using libx264; rendering up to {workers} segment(s) in parallel.")
            args = [
                "--images",
                str(self.images_dir),
                "--audios",
                str(self.audios_dir),
                "--output",
                str(self.output_dir),
                "--width",
                str(self.width),
                "--height",
                str(self.height),
                "--fps",
                str(self.fps),
                "--crf",
                str(self.crf),
                "--codec",
                codec,
                "--workers",
                str(workers),
                "--pattern",
                self.pattern,
                "--zoom-scale",
                str(self.zoom_scale),
                "--base-crop",
                str(self.base_crop),
                "--edge-reach",
                str(self.edge_reach),
                "--face-safe",
                str(self.face_safe),
                "--speed",
                str(self.speed),
                "--pre-silence",
                str(self.pre_silence),
                "--min-motion",
                str(self.min_motion),
                "--combo-radius",
                str(self.combo_radius),
                "--combo-offset-x",
                str(self.combo_offset_x),
                "--combo-offset-y",
                str(self.combo_offset_y),
            ]
            retro_scratch = self.retro_scratch if self.retro_scratches_enabled else 0.0
            retro_dust = self.retro_dust if self.retro_dust_enabled else 0.0
            retro_grain = self.retro_grain if self.retro_grain_enabled else 0.0
            retro_flicker = self.retro_flicker if self.retro_flicker_enabled else 0.0
            retro_vignette = self.retro_vignette if self.retro_vignette_enabled else 0.0
            retro_color_fade = self.retro_color_fade if self.retro_color_fade_enabled else 0.0
            retro_scan_lines = self.retro_scan_lines if self.retro_scan_lines_enabled else 0.0
            retro_enabled = any(
                value > 0
                for value in (
                    retro_scratch,
                    retro_dust,
                    retro_grain,
                    retro_flicker,
                    retro_vignette,
                    retro_color_fade,
                    retro_scan_lines,
                )
            )
            if retro_enabled:
                args.extend(
                    [
                        "--retro-film",
                        "--retro-scratch",
                        str(retro_scratch),
                        "--retro-dust",
                        str(retro_dust),
                        "--retro-flicker",
                        str(retro_flicker),
                        "--retro-grain",
                        str(retro_grain),
                        "--retro-vignette",
                        str(retro_vignette),
                        "--retro-color-fade",
                        str(retro_color_fade),
                        "--retro-scan-lines",
                        str(retro_scan_lines),
                    ]
                )
            if self.random_effects:
                args.append("--random-effects")
            if self.bounce:
                args.append("--bounce")
            if not self.merge_videos:
                args.append("--no-merge")
            if self.segments_in_output_root:
                args.append("--segments-in-output-root")

            os.environ["PYTHONUNBUFFERED"] = "1"
            os.environ["PYTHONIOENCODING"] = "utf-8"
            os.environ["PYTHONUTF8"] = "1"
            python_dir = str(Path(sys.executable).parent)
            os.environ["PATH"] = python_dir + os.pathsep + os.environ.get("PATH", "")
            log_event("VIDEO EFFECT | started internally | " + " ".join(args))
            self.progress.emit("Starting Video Effect render...")
            self.progress.emit("Using bundled internal motion pipeline.")
            self.progress.emit("Options: " + subprocess.list2cmdline(args))
            self.run_internal_pipeline(args)
            if self.cancel_event.is_set():
                self.cancelled.emit("Video Effect stopped. Completed files were kept in the output folder.")
                return
            final_output = self.output_dir / "final_merged.mp4"
            if final_output.is_file():
                if self.merge_videos:
                    session_match = re.match(
                        r"^video_effect_(\d{8}_\d{6})_batch_\d+",
                        self.output_dir.name,
                    )
                    timestamp = (
                        session_match.group(1)
                        if session_match
                        else datetime.now().strftime("%Y%m%d_%H%M%S")
                    )
                    if self.segments_in_output_root:
                        merged_dir = self.output_dir.parent
                    else:
                        merged_dir = self.output_dir / "merged"
                        merged_dir.mkdir(parents=True, exist_ok=True)
                    destination = merged_dir / f"final_merged_{timestamp}.mp4"
                    suffix = 2
                    while destination.exists():
                        destination = merged_dir / f"final_merged_{timestamp}_{suffix:02d}.mp4"
                        suffix += 1
                    shutil.move(str(final_output), str(destination))
                    self.progress.emit(f"Merged video saved: {destination}")
            elapsed = time.strftime("%H:%M:%S", time.gmtime(time.monotonic() - started))
            log_event(f"VIDEO EFFECT | completed | output={self.output_dir} | elapsed={elapsed}")
            self.completed.emit(str(self.output_dir))
        except Exception as exc:
            if self.cancel_event.is_set():
                message = "Video Effect stopped. Completed files were kept in the output folder."
                log_event("VIDEO EFFECT | cancelled")
                self.cancelled.emit(message)
                return
            details = str(exc) if isinstance(exc, RuntimeError) else traceback.format_exc()
            log_event("VIDEO EFFECT | failed\n" + details)
            self.failed.emit(details)

    def emit_pipeline_output(self, text: str) -> None:
        for line in text.splitlines():
            message = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", line).replace("\r", "").strip()
            if not message:
                continue
            self.recent_output.append(message)
            self.recent_output = self.recent_output[-12:]
            segment_match = re.match(r"^\[SEGMENT\] completed (\d+)/(\d+) \| (.+)$", message)
            if segment_match:
                self.segment_progress.emit(
                    int(segment_match.group(1)), int(segment_match.group(2)), segment_match.group(3)
                )
                self.progress.emit(message)
                return
            noisy_prefixes = ("frame_index:", "chunk:", "t:", "MoviePy - Writing audio", "MoviePy - Writing video")
            if message.startswith(noisy_prefixes):
                now = time.monotonic()
                if now - self.last_status_emit >= 1.0:
                    self.last_status_emit = now
                    self.progress.emit("Rendering current segment...")
                continue
            self.progress.emit(message)

    def run_internal_pipeline(self, args: list[str]) -> None:
        import contextlib
        import importlib.util

        worker = self

        class SignalStream:
            def __init__(self) -> None:
                self.buffer = ""

            def write(self, text: str) -> int:
                self.buffer += text
                while "\n" in self.buffer:
                    line, self.buffer = self.buffer.split("\n", 1)
                    worker.emit_pipeline_output(line)
                return len(text)

            def flush(self) -> None:
                if self.buffer:
                    worker.emit_pipeline_output(self.buffer)
                    self.buffer = ""

        spec = importlib.util.spec_from_file_location("voiceover_video_effect_pipeline", self.script_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Could not load bundled Video Effect pipeline: {self.script_path}")
        module = importlib.util.module_from_spec(spec)
        old_argv = sys.argv[:]
        sys.argv = [str(self.script_path), *args]
        stream = SignalStream()
        try:
            with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
                spec.loader.exec_module(module)
                module.CANCEL_CHECK = self.cancel_event.is_set
                module.main()
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 1
            if code:
                exit_detail = ""
                if exc.code is not None and not isinstance(exc.code, int):
                    exit_detail = str(exc.code).strip()
                tail = "\n".join(self.recent_output[-8:])
                details = "\n".join(part for part in (exit_detail, tail) if part)
                raise RuntimeError(
                    f"Video Effect pipeline exited with code {code}."
                    + (f"\n\n{details}" if details else "")
                ) from exc
        finally:
            stream.flush()
            sys.argv = old_argv

    def detect_gpu_codec(self) -> str:
        try:
            result = subprocess.run(
                [ffmpeg_executable(), "-hide_banner", "-encoders"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=0x08000000 if sys.platform == "win32" else 0,
            )
            output = result.stdout + result.stderr
        except Exception:
            return ""
        for candidate in ("h264_nvenc", "hevc_nvenc", "h264_qsv", "h264_amf"):
            if candidate in output and self.test_video_encoder(candidate):
                return candidate
        return ""

    def test_video_encoder(self, codec: str) -> bool:
        try:
            result = subprocess.run(
                [
                    ffmpeg_executable(),
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "color=c=black:s=256x256:d=0.1",
                    "-c:v",
                    codec,
                    "-frames:v",
                    "1",
                    "-f",
                    "null",
                    "-",
                ],
                capture_output=True,
                text=True,
                timeout=15,
                creationflags=0x08000000 if sys.platform == "win32" else 0,
            )
            return result.returncode == 0
        except Exception:
            return False


class Zonos2Worker(QObject):
    progress = Signal(int, int, str)
    segment_status = Signal(int, str)
    completed = Signal(str)
    cancelled = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        server_url: str,
        input_path: Path,
        output_dir: Path,
        output_format: str,
        language: str,
        speed: float,
        seed: int,
        accurate_mode: bool,
        voice_id: str = "",
        temperature: float = 1.15,
        topk: int = 106,
        min_p: float = 0.18,
        repetition_penalty: float = 1.2,
        clean_speaker_background: bool = False,
        segment_limit: int | None = None,
        cooldown_seconds: int = 0,
        start_position: int = 1,
        end_position: int | None = None,
        overwrite: bool = False,
        normalize_audio: bool = False,
        reference_audio: str = "",
        session_id: str = "",
    ) -> None:
        super().__init__()
        self.server_url = server_url.rstrip("/")
        self.input_path = input_path
        self.output_dir = output_dir
        self.output_format = output_format
        self.language = language
        self.speed = speed
        self.seed = seed
        self.accurate_mode = accurate_mode
        self.voice_id = voice_id
        self.reference_audio = reference_audio
        self.session_id = session_id
        self.temperature = temperature
        self.topk = topk
        self.min_p = min_p
        self.repetition_penalty = repetition_penalty
        self.clean_speaker_background = clean_speaker_background
        self.segment_limit = segment_limit
        self.cooldown_seconds = cooldown_seconds
        self.start_position = start_position
        self.end_position = end_position
        self.overwrite = overwrite
        self.normalize_audio = normalize_audio
        self.cancel_event = threading.Event()

    def request_cancel(self) -> None:
        self.cancel_event.set()
        log_event("ZONOS2 | cancellation requested")

    def run(self) -> None:
        manifest: list[dict] = []
        generated_files: list[Path] = []
        try:
            import numpy as np
            import soundfile as sf

            configure_ffmpeg()
            segments = parse_input(self.input_path)
            if self.segment_limit:
                segments = segments[: self.segment_limit]
            end_position = min(self.end_position or len(segments), len(segments))
            self.output_dir.mkdir(parents=True, exist_ok=True)
            width = max(3, len(str(len(segments))))
            endpoint = self.server_url + "/tts/generate"
            voice_id = self.voice_id
            request_headers = {"Content-Type": "application/json"}
            if self.session_id:
                request_headers["X-TTS-Session-ID"] = self.session_id
            if self.reference_audio:
                audio_path = Path(self.reference_audio)
                cache_payload = {
                    "label": audio_path.stem,
                    "speaker_audio_name": audio_path.name,
                    "speaker_audio_base64": base64.b64encode(audio_path.read_bytes()).decode("ascii"),
                }
                cache_request = urllib.request.Request(
                    self.server_url + "/tts/speakers",
                    data=json.dumps(cache_payload).encode("utf-8"),
                    headers=request_headers,
                    method="POST",
                )
                with urllib.request.urlopen(cache_request, timeout=600) as response:
                    speaker = json.loads(response.read().decode("utf-8"))
                    voice_id = speaker.get("id") or speaker.get("speaker_id")
                    if not voice_id:
                        raise RuntimeError(
                            "ZONOS2 cached the reference voice but did not return a speaker ID."
                        )
            log_event(f"ZONOS2 | started | endpoint={endpoint} | model={DEFAULT_ZONOS2_MODEL}")
            for position, segment in enumerate(segments, start=1):
                if position < self.start_position or position > end_position:
                    continue
                if self.cancel_event.is_set():
                    self.finish_cancelled(manifest)
                    return
                stem = f"{position:0{width}d}"
                destination = self.output_dir / f"{stem}.{self.output_format}"
                if not self.overwrite and destination.is_file() and destination.stat().st_size > 0:
                    record = asdict(segment)
                    record["file"] = destination.name
                    manifest.append(record)
                    self.progress.emit(position, len(segments), f"Skipping completed {destination.name}")
                    self.segment_status.emit(position, "Completed")
                    continue
                self.progress.emit(position, len(segments), segment.text)
                payload = {
                    "text": segment.text,
                    "stream": False,
                    "speed": self.speed,
                    "seed": self.seed + position - 1,
                    "accurate_mode": self.accurate_mode,
                    "temperature": self.temperature,
                    "topk": self.topk,
                    "min_p": self.min_p,
                    "repetition_penalty": self.repetition_penalty,
                    "clean_speaker_background": self.clean_speaker_background,
                }
                if voice_id:
                    payload["speaker_embedding_id"] = voice_id
                if self.language == "raw":
                    payload["text_normalization"] = False
                else:
                    payload["language"] = self.language
                    payload["text_normalization"] = True
                request = urllib.request.Request(
                    endpoint,
                    data=json.dumps(payload).encode("utf-8"),
                    headers=request_headers,
                    method="POST",
                )
                try:
                    with urllib.request.urlopen(request, timeout=600) as response:
                        audio_bytes = response.read()
                        sample_rate = int(response.headers.get("X-Audio-Sample-Rate", "44100"))
                except urllib.error.HTTPError as exc:
                    details = exc.read().decode("utf-8", errors="replace")
                    raise RuntimeError(f"ZONOS2 server returned HTTP {exc.code}: {details}") from exc
                audio = np.frombuffer(audio_bytes, dtype="<f4")
                if not audio.size:
                    raise RuntimeError("ZONOS2 server returned empty audio.")
                wav_path = self.output_dir / f"{stem}.wav"
                sf.write(wav_path, audio, sample_rate)
                destination = wav_path
                if self.output_format == "mp3":
                    destination = self.output_dir / f"{stem}.mp3"
                    result = subprocess.run(
                        [
                            ffmpeg_executable(), "-y", "-i", str(wav_path),
                            "-codec:a", "libmp3lame", "-b:a", "192k", str(destination),
                        ],
                        capture_output=True,
                        text=True,
                        creationflags=0x08000000,
                    )
                    wav_path.unlink(missing_ok=True)
                    if result.returncode != 0:
                        raise RuntimeError(f"MP3 conversion failed:\n{result.stderr[-1000:]}")
                record = asdict(segment)
                record["file"] = destination.name
                manifest.append(record)
                generated_files.append(destination)
                self.segment_status.emit(position, "Completed")
                (self.output_dir / "manifest.partial.json").write_text(
                    json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                if self.cooldown_seconds and position < end_position:
                    self.progress.emit(
                        position, len(segments), f"Cooling down for {self.cooldown_seconds} second(s)..."
                    )
                    if self.cancel_event.wait(self.cooldown_seconds):
                        self.finish_cancelled(manifest)
                        return
            numbered = [
                self.output_dir / f"{position:0{width}d}.{self.output_format}"
                for position in range(1, len(segments) + 1)
            ]
            if self.normalize_audio and all(path.is_file() for path in numbered):
                normalize_completed_batch(
                    numbered,
                    progress=lambda message: self.progress.emit(len(segments), len(segments), message),
                    cancelled=self.cancel_event.is_set,
                    originals_dir=self.output_dir / "_original_zonos2",
                    original_files=generated_files,
                    report_path=self.output_dir / "loudness_before_after.csv",
                )
            (self.output_dir / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            (self.output_dir / "manifest.partial.json").unlink(missing_ok=True)
            log_event(f"ZONOS2 | completed | output={self.output_dir}")
            self.completed.emit(str(self.output_dir))
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            message = f"ZONOS2 server returned HTTP {exc.code}: {details}"
            log_event("ZONOS2 | HTTP request failed\n" + message)
            self.failed.emit(message)
        except urllib.error.URLError:
            details = zonos2_connection_error(self.server_url)
            log_event("ZONOS2 | connection failed\n" + traceback.format_exc())
            self.failed.emit(details)
        except Exception:
            details = traceback.format_exc()
            log_event("ZONOS2 | failed\n" + details)
            self.failed.emit(details)

    def finish_cancelled(self, manifest: list[dict]) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "manifest.partial.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        message = f"ZONOS2 stopped safely. Kept {len(manifest)} completed audio file(s)."
        log_event("ZONOS2 | " + message)
        self.cancelled.emit(message)


class CaptionPreviewWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.config: dict = {}
        self.setMinimumHeight(260)

    def set_config(self, config: dict) -> None:
        self.config = config
        self.update()

    def debug_snapshot(self) -> str:
        style = self.config.get("style", {})
        layout = self.config.get("layout", {})
        return (
            f"font={style.get('font_family')} size={style.get('font_size')} "
            f"highlight={style.get('highlight_type')} radius={style.get('corner_radius')} "
            f"youtube_auto={layout.get('youtube_auto_position', False)} "
            "demo=Your caption lights up word by word"
        )

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(0, 0, -1, -1)
        painter.fillRect(rect, QColor("#111821"))
        style = self.config.get("style", {})
        layout = self.config.get("layout", {})
        youtube_auto = bool(layout.get("youtube_auto_position", False))
        if layout.get("safe_area_preview", True):
            pen = QPen(QColor("#526070"))
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawRect(rect.adjusted(18, 18, -18, -18))
        if youtube_auto:
            controls_height = max(14, round(rect.height() * 0.065))
            painter.fillRect(
                QRectF(0, rect.height() - controls_height, rect.width(), controls_height),
                QColor(0, 0, 0, 105),
            )

        words = ["Your", "caption", "lights", "up", "word", "by", "word"]
        active_index = 3
        font = QFont(str(style.get("font_family") or "Arial"))
        font.setPixelSize(int(style.get("font_size") or 54))
        font.setBold(bool(style.get("bold", True)))
        font.setItalic(bool(style.get("italic", False)))
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, float(style.get("letter_spacing", 0)))
        display_words = [word.upper() if style.get("uppercase") else word for word in words]
        padding_x = int(style.get("padding_x", 16))
        padding_y = int(style.get("padding_y", 8))
        radius = int(style.get("corner_radius", 12))
        available_width = max(120, rect.width() - 64)
        while True:
            painter.setFont(font)
            metrics = QFontMetrics(font)
            space_width = metrics.horizontalAdvance(" ")
            word_widths = [metrics.horizontalAdvance(word) for word in display_words]
            text_width = sum(word_widths) + space_width * (len(words) - 1)
            box_width = text_width + padding_x * 2
            if box_width <= available_width or font.pixelSize() <= 26:
                break
            font.setPixelSize(font.pixelSize() - 2)
        line_height = metrics.height()
        box_height = line_height + padding_y * 2
        alignment = layout.get("alignment", "Center")
        if alignment == "Left":
            x = int(layout.get("margin_x", 60))
        elif alignment == "Right":
            x = rect.width() - int(layout.get("margin_x", 60)) - box_width
        else:
            x = (rect.width() - box_width) // 2
        anchor = layout.get("anchor", "Bottom")
        if anchor == "Top":
            y = 42
        elif anchor == "Middle":
            y = (rect.height() - box_height) // 2
        else:
            preview_scale = rect.height() / 1080.0
            margin_bottom = max(0, round(int(layout.get("margin_bottom", 90)) * preview_scale))
            if youtube_auto:
                controls_height = max(14, round(rect.height() * 0.065))
                margin_bottom = max(margin_bottom, controls_height + 6)
            y = rect.height() - margin_bottom - box_height
            y = max(34, y)

        background_mode = style.get("background_mode", "None")
        if background_mode == "Line box":
            bg = QColor(str(style.get("background_color", "#000000")))
            bg.setAlphaF(float(style.get("background_opacity", 0.45)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(bg)
            painter.drawRoundedRect(QRectF(x, y, box_width, box_height), radius, radius)

        base_color = self.dim_color(str(style.get("base_color", "#FFFFFF")), float(style.get("inactive_dim", 1.0)))
        active_color = QColor(str(style.get("active_color", "#FF8A00")))
        outline_color = QColor(str(style.get("outline_color", "#000000")))
        outline_width = max(0, int(style.get("outline_width", 3)))
        highlight_type = style.get("highlight_type", "Active color")
        cursor_x = x + padding_x
        baseline = y + padding_y + metrics.ascent()
        for index, word in enumerate(display_words):
            is_active = index == active_index
            active_box = background_mode == "Active word box" or highlight_type == "Active background"
            word_width = word_widths[index]
            if is_active and active_box and highlight_type != "None":
                box_color = QColor(str(style.get("background_color", "#000000")))
                box_color.setAlphaF(float(style.get("background_opacity", 0.9)))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(box_color)
                painter.drawRoundedRect(
                    QRectF(cursor_x - padding_x // 2, y, word_width + padding_x, box_height),
                    radius,
                    radius,
                )
            if is_active and highlight_type == "Progressive sweep":
                sweep_color = QColor(str(style.get("active_color", "#FF8A00")))
                sweep_color.setAlphaF(0.35)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(sweep_color)
                painter.drawRoundedRect(
                    QRectF(cursor_x - 4, y + box_height - 10, word_width + 8, 8),
                    4,
                    4,
                )
            fill = active_color if is_active and highlight_type != "None" else base_color
            path = QPainterPath()
            path.addText(cursor_x, baseline, font, word)
            if outline_width:
                painter.setPen(QPen(outline_color, outline_width * 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(path)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill)
            painter.drawPath(path)
            cursor_x += word_width + space_width

    def dim_color(self, value: str, dim: float) -> QColor:
        color = QColor(value)
        if not color.isValid():
            color = QColor("#FFFFFF")
        dim = max(0.0, min(1.0, dim))
        bg = 17
        return QColor(
            round(bg + (color.red() - bg) * dim),
            round(bg + (color.green() - bg) * dim),
            round(bg + (color.blue() - bg) * dim),
        )


class WatermarkPreviewWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.config: dict = {}
        self.setMinimumHeight(300)

    def set_config(self, config: dict) -> None:
        self.config = config
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        frame = self.rect().adjusted(0, 0, -1, -1)
        gradient = QLinearGradient(0, 0, frame.width(), frame.height())
        gradient.setColorAt(0, QColor("#25364A"))
        gradient.setColorAt(1, QColor("#10151D"))
        painter.fillRect(frame, gradient)
        painter.setPen(QPen(QColor("#526070"), 1, Qt.PenStyle.DashLine))
        painter.drawRect(frame.adjusted(18, 18, -18, -18))
        if not self.config:
            return
        style = self.config["style"]
        name = (self.config.get("names") or ["Your Channel"])[0]
        font = QFont(style["font"])
        font.setPixelSize(max(12, round(style["font_size"] * frame.height() / 720)))
        font.setBold(style.get("bold", False))
        font.setItalic(style.get("italic", False))
        painter.setFont(font)
        metrics = QFontMetrics(font)
        px, py = 10, 6
        width, height = metrics.horizontalAdvance(name) + px * 2, metrics.height() + py * 2
        edge_x = max(8, round(self.config["padding_x"] * frame.width() / 1280))
        edge_y = max(8, round(self.config["padding_y"] * frame.height() / 720))
        position = self.config["position"]
        x = edge_x if "Left" in position else frame.width() - edge_x - width
        y = edge_y if "Top" in position else frame.height() - edge_y - height
        mode = style["background"]
        if mode != "None":
            bg = QColor(style["background_color"])
            bg.setAlphaF(style["background_opacity"])
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(bg)
            radius = 18 if mode == "Much rounded" else 8 if mode in {"Round", "Rounded"} else 0
            painter.drawRoundedRect(QRectF(x, y, width, height), radius, radius)
        painter.setPen(QColor(style["text_color"]))
        painter.drawText(QRectF(x + px, y + py, width - px * 2, height - py * 2),
                         Qt.AlignmentFlag.AlignCenter, name)
        subscribe = self.config.get("subscribe", {})
        if subscribe.get("video"):
            sw = round(frame.width() * subscribe["scale"] / 100)
            sh = max(34, round(sw * 0.32))
            sx = edge_x if "Left" in subscribe["position"] else frame.width() - edge_x - sw
            sy = edge_y if "Top" in subscribe["position"] else frame.height() - edge_y - sh
            painter.fillRect(QRectF(sx, sy, sw, sh), QColor(220, 30, 45, 210))
            painter.setPen(QColor("white"))
            painter.drawText(QRectF(sx, sy, sw, sh), Qt.AlignmentFlag.AlignCenter, "SUBSCRIBE")


class ChromaColorPickerLabel(QLabel):
    colorPicked = Signal(str)

    def __init__(self) -> None:
        super().__init__("Capture a subscribe-video frame,\nthen click the image to pick a key color.")
        self.source_pixmap = QPixmap()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(True)
        self.setFixedHeight(72)
        self.setMinimumWidth(260)
        self.setStyleSheet("border: 1px solid #526070; background: #111821;")

    def set_source(self, path: str) -> bool:
        pixmap = QPixmap(path)
        if pixmap.isNull():
            return False
        self.source_pixmap = pixmap
        self.refresh_pixmap()
        return True

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.refresh_pixmap()

    def refresh_pixmap(self) -> None:
        if not self.source_pixmap.isNull():
            self.setPixmap(self.source_pixmap.scaled(
                max(1, self.width() - 8), max(1, self.height() - 8),
                Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation,
            ))

    def mousePressEvent(self, event) -> None:
        shown = self.pixmap()
        if self.source_pixmap.isNull() or shown.isNull():
            return super().mousePressEvent(event)
        left = (self.width() - shown.width()) / 2
        top = (self.height() - shown.height()) / 2
        x = event.position().x() - left
        y = event.position().y() - top
        if not (0 <= x < shown.width() and 0 <= y < shown.height()):
            return
        source_x = min(self.source_pixmap.width() - 1, int(x * self.source_pixmap.width() / shown.width()))
        source_y = min(self.source_pixmap.height() - 1, int(y * self.source_pixmap.height() / shown.height()))
        color = self.source_pixmap.toImage().pixelColor(source_x, source_y)
        self.colorPicked.emit(color.name().upper())


class WatermarkWorker(QObject):
    progress = Signal(int, int, str)
    render_progress = Signal(int, str)
    completed = Signal(str)
    failed = Signal(str)
    cancelled = Signal(str)

    def __init__(self, jobs: list[dict], config: dict) -> None:
        super().__init__()
        self.jobs = jobs
        self.config = config
        self._cancelled = False
        self.process: subprocess.Popen | None = None

    def cancel(self) -> None:
        self._cancelled = True
        if self.process and self.process.poll() is None:
            self.process.terminate()

    def _run_ffmpeg_with_progress(
        self,
        command: list[str],
        duration: float,
        completed_units: float,
        total_units: float,
        message_prefix: str,
        batch_started: float,
        unit_weight: float = 1.0,
    ) -> str:
        self.process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            encoding="utf-8", errors="replace",
            creationflags=0x08000000 if sys.platform == "win32" else 0,
        )
        output_lines = []
        assert self.process.stdout is not None
        for line in self.process.stdout:
            output_lines.append(line)
            if len(output_lines) > 500:
                output_lines.pop(0)
            stripped = line.strip()
            if stripped.startswith(("out_time_ms=", "out_time_us=")):
                try:
                    rendered = int(stripped.split("=", 1)[1].strip()) / 1_000_000
                except ValueError:
                    continue
                fraction = min(1.0, rendered / max(0.01, duration))
                overall = min(
                    1.0,
                    (completed_units + fraction * unit_weight) / max(1.0, total_units),
                )
                elapsed = time.monotonic() - batch_started
                eta = elapsed * (1 - overall) / overall if overall > 0 else 0
                elapsed_text = time.strftime("%H:%M:%S", time.gmtime(elapsed))
                eta_text = time.strftime("%H:%M:%S", time.gmtime(max(0, eta)))
                self.render_progress.emit(
                    round(overall * 100),
                    f"{message_prefix} | Elapsed {elapsed_text} | ETA {eta_text}",
                )
        self.process.wait()
        if self._cancelled:
            raise InterruptedError
        error = "".join(output_lines)
        if self.process.returncode:
            raise RuntimeError(error[-5000:])
        return error

    def run(self) -> None:
        try:
            batch_started = time.monotonic()
            total_units = sum(
                len(job.get("variants", [])) or 1 for job in self.jobs
            )
            done_units = 0.0
            for index, job in enumerate(self.jobs, 1):
                if self._cancelled:
                    self.cancelled.emit("Watermark batch stopped.")
                    return
                selected_codec = self.config.get("codec", "auto")
                if selected_codec == "auto":
                    codecs = [require_video_gpu_codec()]
                else:
                    codecs = [selected_codec]
                errors = []
                for codec in codecs:
                    attempt_config = dict(self.config)
                    attempt_config["codec"] = codec
                    base_output = job.get("base_output")
                    variants = job.get("variants", [])
                    trailer_video = str(attempt_config.get("trailer", {}).get("video", "")).strip()
                    duration = media_duration_seconds(job["input"])
                    if trailer_video:
                        duration += media_duration_seconds(trailer_video)
                    if variants:
                        try:
                            prepared_variants = []
                            for variant_index, variant in enumerate(variants, 1):
                                overlay_dir = Path(variant["output"]).parent / "_watermark_assets"
                                overlay = create_channel_name_overlay_image(
                                    variant["name"], attempt_config, overlay_dir,
                                    Path(variant["output"]).stem + "_channel",
                                )
                                prepared_variants.append({
                                    "name": variant["name"],
                                    "output": variant["output"],
                                    "overlay": str(overlay),
                                })
                            max_parallel_outputs = 3
                            groups = [
                                prepared_variants[start:start + max_parallel_outputs]
                                for start in range(0, len(prepared_variants), max_parallel_outputs)
                            ]
                            for group_index, group in enumerate(groups, 1):
                                self.progress.emit(
                                    round(done_units), round(total_units),
                                    f"Fast multi-output group {group_index}/{len(groups)}: "
                                    + ", ".join(item["name"] for item in group),
                                )
                                self._run_ffmpeg_with_progress(
                                    build_watermark_ffmpeg_command({
                                        "input": job["input"],
                                        "output": group[0]["output"],
                                        "logo": job.get("logo", ""),
                                        "caption": str(job.get("caption", "")),
                                        "channel_variants": group,
                                    }, attempt_config),
                                    duration,
                                    done_units,
                                    total_units,
                                    f"GPU multi-output {codec} | group "
                                    f"{group_index}/{len(groups)}",
                                    batch_started,
                                    unit_weight=len(group),
                                )
                                done_units += len(group)
                            break
                        except Exception as exc:
                            errors.append(f"\nEncoder {codec} failed:\n{str(exc)[-3500:]}")
                    else:
                        self.progress.emit(
                            round(done_units), round(total_units),
                            f"Rendering {Path(job['output']).name} with {codec}",
                        )
                        try:
                            self._run_ffmpeg_with_progress(
                                build_watermark_ffmpeg_command(job, attempt_config),
                                duration, done_units, total_units,
                                f"GPU encode {codec} | {index}/{len(self.jobs)}",
                                batch_started,
                            )
                            done_units += 1
                            break
                        except Exception as exc:
                            errors.append(f"\nEncoder {codec} failed:\n{str(exc)[-3500:]}")
                    if not errors or errors[-1] == "":
                        break
                    if self._cancelled:
                        self.cancelled.emit("Watermark batch stopped.")
                        return
                else:
                    raise RuntimeError("".join(errors)[-7000:])
                self.progress.emit(round(done_units), round(total_units), Path(job.get("output", job.get("base_output", ""))).name)
            elapsed = time.monotonic() - batch_started
            self.render_progress.emit(
                100, f"Completed in {time.strftime('%H:%M:%S', time.gmtime(elapsed))}"
            )
            self.completed.emit(str(Path(self.jobs[0]["output"]).parent))
        except Exception:
            self.failed.emit(traceback.format_exc())


class VideoMaskLabel(QLabel):
    maskChanged = Signal(object)

    def __init__(self, placeholder: str = "") -> None:
        super().__init__(placeholder)
        self.source_pixmap = QPixmap()
        self.source_mask = QRectF()
        self.drag_start = None
        self.setMouseTracking(True)

    def set_source(self, pixmap: QPixmap, mask: tuple[int, int, int, int] | None = None) -> None:
        self.source_pixmap = pixmap
        if mask:
            self.source_mask = QRectF(*mask)
        self.update()

    def _display_rect(self) -> QRectF:
        if self.source_pixmap.isNull():
            return QRectF()
        scaled = self.source_pixmap.size().scaled(
            self.size(), Qt.AspectRatioMode.KeepAspectRatio
        )
        return QRectF(
            (self.width() - scaled.width()) / 2,
            (self.height() - scaled.height()) / 2,
            scaled.width(), scaled.height(),
        )

    def _to_source(self, point) -> tuple[float, float]:
        shown = self._display_rect()
        x = min(max(point.x(), shown.left()), shown.right())
        y = min(max(point.y(), shown.top()), shown.bottom())
        return (
            (x - shown.left()) * self.source_pixmap.width() / max(1, shown.width()),
            (y - shown.top()) * self.source_pixmap.height() / max(1, shown.height()),
        )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and not self.source_pixmap.isNull():
            self.drag_start = self._to_source(event.position())
            self.source_mask = QRectF(self.drag_start[0], self.drag_start[1], 1, 1)
            self.update()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self.drag_start is not None:
            current = self._to_source(event.position())
            self.source_mask = QRectF(
                min(self.drag_start[0], current[0]),
                min(self.drag_start[1], current[1]),
                abs(current[0] - self.drag_start[0]),
                abs(current[1] - self.drag_start[1]),
            )
            self.update()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self.drag_start is not None:
            self.mouseMoveEvent(event)
            self.drag_start = None
            rect = self.source_mask.toAlignedRect()
            if rect.width() >= 8 and rect.height() >= 8:
                self.maskChanged.emit((rect.x(), rect.y(), rect.width(), rect.height()))
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:
        if self.source_pixmap.isNull():
            return super().paintEvent(event)
        painter = QPainter(self)
        shown = self._display_rect()
        painter.drawPixmap(shown.toRect(), self.source_pixmap)
        if not self.source_mask.isEmpty():
            sx = shown.width() / max(1, self.source_pixmap.width())
            sy = shown.height() / max(1, self.source_pixmap.height())
            mask = QRectF(
                shown.left() + self.source_mask.x() * sx,
                shown.top() + self.source_mask.y() * sy,
                self.source_mask.width() * sx,
                self.source_mask.height() * sy,
            )
            painter.fillRect(mask, QColor(255, 45, 45, 55))
            painter.setPen(QPen(QColor("#ff4545"), 2))
            painter.drawRect(mask)


class GeminiLogoWorker(QObject):
    progress = Signal(int, str)
    completed = Signal(str, str, str, str, object)
    failed = Signal(str)

    def __init__(
        self, source: str, mask_output: str, alpha_output: str,
        temporal_output: str, lama_output: str,
        logo_percent: int, margin_percent: int,
        manual_box: tuple[int, int, int, int] | None = None,
        mode: str = "full",
    ) -> None:
        super().__init__()
        self.source = source
        self.mask_output = mask_output
        self.alpha_output = alpha_output
        self.temporal_output = temporal_output
        self.lama_output = lama_output
        self.logo_percent = logo_percent
        self.margin_percent = margin_percent
        self.manual_box = manual_box
        self.mode = mode
        self.process: subprocess.Popen | None = None
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True
        if self.process and self.process.poll() is None:
            self.process.terminate()

    def run(self) -> None:
        try:
            if self.mode == "stable":
                if not self.manual_box:
                    raise RuntimeError("Draw a tight logo mask before running Stable Clean.")
                self._run_stable_clean(self.manual_box)
                quality = score_gemini_video_residual(
                    self.source, self.temporal_output, self.manual_box
                )
                quality["evaluated"] = "stable"
                self.completed.emit(
                    self.mask_output, self.alpha_output, self.temporal_output,
                    self.lama_output, quality,
                )
                return
            if self.mode == "lama":
                if not self.manual_box:
                    raise RuntimeError("Draw a mask before rerunning LaMa AI.")
                if os.environ.get("VOICEOVER_DEFAULT_DEVICE", "cuda") == "cpu":
                    self.progress.emit(2, "CPU mode · using Stable Clean fallback for LaMa AI...")
                    self._run_stable_clean(self.manual_box)
                    quality = score_gemini_video_residual(
                        self.source, self.temporal_output, self.manual_box
                    )
                    quality["evaluated"] = "stable"
                    self.completed.emit(
                        self.mask_output, self.alpha_output, self.temporal_output,
                        self.lama_output, quality,
                    )
                    return
                codec = require_video_gpu_codec()
                self._run_lama_inpaint(self.manual_box, codec)
                quality = score_gemini_video_residual(
                    self.source, self.lama_output, self.manual_box
                )
                quality["evaluated"] = "lama"
                self.completed.emit(
                    self.mask_output, self.alpha_output, self.temporal_output,
                    self.lama_output, quality,
                )
                return
            if self.mode == "temporal":
                if not self.manual_box:
                    raise RuntimeError("Draw a mask before rerunning AI Temporal.")
                self.progress.emit(2, "Using Stable Clean for AI Temporal...")
                self._run_stable_clean(self.manual_box)
                quality = score_gemini_video_residual(
                    self.source, self.temporal_output, self.manual_box
                )
                quality["evaluated"] = "stable"
                self.completed.emit(
                    self.mask_output, self.alpha_output, self.temporal_output,
                    self.lama_output, quality,
                )
                return
            width, height = media_video_size(self.source)
            x, y, box_w, box_h = self.manual_box or gemini_logo_box(
                width, height, self.logo_percent, self.margin_percent
            )
            self._run_stable_clean((x, y, box_w, box_h))
            quality = score_gemini_video_residual(
                self.source, self.temporal_output, (x, y, box_w, box_h)
            )
            quality["evaluated"] = "stable"
            self.progress.emit(100, "Stable Clean complete.")
            self.completed.emit(
                self.mask_output, self.alpha_output, self.temporal_output,
                self.lama_output, quality,
            )
        except Exception:
            self.failed.emit(traceback.format_exc())

    def _run_official_gwr(self) -> None:
        repo = APP_ROOT / "vendor" / "gemini-watermark-remover"
        runner = APP_ROOT / "premium_safe_runner.mjs"
        page = repo / "dist" / "video-preview.html"
        if not runner.is_file() or not page.is_file():
            raise RuntimeError(
                "The Premium Safe engine is not ready. Reinstall the video processing component."
            )
        node = shutil.which("node.exe" if sys.platform == "win32" else "node")
        if not node:
            raise RuntimeError("The Node runtime for Premium Safe was not found.")

        last_error = ""
        for attempt in range(1, 3):
            if self._cancelled:
                raise RuntimeError("Premium Safe was stopped.")
            output = Path(self.alpha_output)
            if output.exists():
                output.unlink()
            self.progress.emit(
                52,
                "Premium Safe · analytical alpha"
                + (f" · retry {attempt}" if attempt > 1 else ""),
            )
            self.process = subprocess.Popen(
                [node, str(runner), self.source, self.alpha_output],
                cwd=str(APP_ROOT), stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                errors="replace",
                creationflags=0x08000000 if sys.platform == "win32" else 0,
            )
            lines: list[str] = []
            assert self.process.stdout is not None
            for line in self.process.stdout:
                lines.append(line)
                if len(lines) > 500:
                    lines.pop(0)
                if line.strip().startswith("{"):
                    self.progress.emit(75, "Premium Safe · validating analytical output...")
            self.process.wait()
            if self._cancelled:
                raise RuntimeError("Premium Safe was stopped.")
            if self.process.returncode == 0 and output.is_file():
                return
            last_error = "".join(lines)[-6000:]
            if attempt < 2:
                self.progress.emit(55, "Premium Safe encountered a temporary error · retrying...")
        safe_error = re.sub(r"(?i)gwr", "Premium Safe", last_error)
        safe_error = re.sub(
            r"https?://(?:127\.0\.0\.1|localhost):\d+(?:/\S*)?",
            "internal processing service",
            safe_error,
        )
        raise RuntimeError("Premium Safe failed after two attempts:\n" + safe_error)

    def _run_reverse_alpha(
        self, box: tuple[int, int, int, int], codec: str, duration: float
    ) -> None:
        import cv2
        import numpy as np

        capture = cv2.VideoCapture(self.source)
        if not capture.isOpened():
            raise RuntimeError("Could not decode the trailer for Reverse Alpha processing.")
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 30.0)
        frame_count = max(1, int(capture.get(cv2.CAP_PROP_FRAME_COUNT)))
        alpha_asset = APP_RUNTIME_ROOT / "assets" / (
            "gemini_bg_96.png" if max(box[2], box[3]) > 70 else "gemini_bg_48.png"
        )
        alpha_image = cv2.imread(str(alpha_asset), cv2.IMREAD_GRAYSCALE)
        if alpha_image is None:
            capture.release()
            raise RuntimeError(f"Gemini alpha map is missing: {alpha_asset}")
        x, y, box_w, box_h = box
        alpha = cv2.resize(alpha_image, (box_w, box_h), interpolation=cv2.INTER_LINEAR)
        alpha = alpha.astype(np.float32) / 255.0
        alpha[alpha < 0.002] = 0.0
        alpha = np.minimum(alpha, 0.97)
        estimate_mask = ((alpha > 0.015).astype(np.uint8) * 255)
        command = [
            ffmpeg_executable(), "-y", "-hide_banner", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{width}x{height}",
            "-r", f"{fps:.6f}", "-i", "pipe:0", "-i", self.source,
            "-map", "0:v:0", "-map", "1:a?", "-c:v", codec,
        ]
        if codec in {"h264_nvenc", "hevc_nvenc"}:
            command.extend(["-preset", "p4", "-cq", "18"])
        elif codec == "h264_qsv":
            command.extend(["-global_quality", "18"])
        elif codec == "h264_amf":
            command.extend(["-quality", "quality"])
        command.extend([
            "-c:a", "copy", "-movflags", "+faststart", "-shortest", self.alpha_output,
        ])
        self.process = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE, creationflags=0x08000000 if sys.platform == "win32" else 0,
        )
        processed = 0
        assert self.process.stdin is not None
        while not self._cancelled:
            ok, frame = capture.read()
            if not ok:
                break
            roi = frame[y:y + box_h, x:x + box_w].astype(np.float32)
            # Estimate the unmarked local background only to recover the actual
            # watermark strength. Video compression makes its alpha vary by frame;
            # blindly applying the calibration map causes a black inverse logo.
            restored, _strength = reverse_alpha_gemini_roi(
                roi.astype(np.uint8), alpha, estimate_mask
            )
            frame[y:y + box_h, x:x + box_w] = restored
            try:
                self.process.stdin.write(frame.tobytes())
            except BrokenPipeError:
                break
            processed += 1
            if processed % max(1, round(fps / 2)) == 0:
                percent = 50 + min(49, round(processed * 50 / frame_count))
                self.progress.emit(percent, f"Reverse Alpha + GPU encode · {percent}%")
        capture.release()
        try:
            self.process.stdin.close()
        except (BrokenPipeError, OSError):
            pass
        stderr = self.process.stderr.read().decode("utf-8", errors="replace") if self.process.stderr else ""
        self.process.wait()
        if self._cancelled:
            raise RuntimeError("Logo removal was stopped.")
        if self.process.returncode:
            raise RuntimeError(f"Reverse Alpha rendering failed:\n{stderr[-4000:]}")



    def _run_stable_clean(self, box: tuple[int, int, int, int]) -> None:
        """Run scene-isolated LaMa anchors with bidirectional flow propagation."""
        import cv2

        codec = require_video_gpu_codec()
        runner_modules = list(APP_ROOT.glob("stable_clean_runner*.pyd"))
        model_path = APP_ROOT / "models" / "lama" / "big-lama.pt"
        if not runner_modules or not model_path.is_file():
            raise RuntimeError(
                "Stable Clean is not ready; models/lama/big-lama.pt is missing."
            )
        capture = cv2.VideoCapture(self.source)
        if not capture.isOpened():
            raise RuntimeError("Cannot open the original video for Stable Clean.")
        frame_count = max(1, int(capture.get(cv2.CAP_PROP_FRAME_COUNT)))
        capture.release()
        self.progress.emit(3, "Stable Clean · detecting hard cuts...")
        scene_ranges = detect_video_scene_ranges(self.source, frame_count)
        scene_text = ",".join(f"{start}:{end}" for start, end in scene_ranges)
        bundled_python = APP_ROOT / ".conda-env" / (
            "python.exe" if sys.platform == "win32" else "bin/python"
        )
        python_executable = str(
            bundled_python if bundled_python.is_file() else Path(sys.executable)
        )
        temp_parent = config_dir() / "tools_temp"
        temp_parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="stable_clean_", dir=str(temp_parent)) as temp:
            silent_output = Path(temp) / "stable_clean_silent.mp4"
            command = [
                python_executable, "-c",
                "import stable_clean_runner; raise SystemExit(stable_clean_runner.main())",
                "--input", self.source,
                "--output", str(silent_output),
                "--model", str(model_path),
                "--ffmpeg", ffmpeg_executable(),
                "--box", ",".join(str(value) for value in box),
                "--scene-ranges", scene_text,
                "--anchor-stride", "6",
                "--alpha-asset", str(
                    APP_RUNTIME_ROOT / "assets" / (
                        "gemini_bg_96.png" if max(box[2], box[3]) > 70
                        else "gemini_bg_48.png"
                    )
                ),
            ]
            environment = os.environ.copy()
            environment["PYTHONUNBUFFERED"] = "1"
            environment.setdefault("CUDA_MODULE_LOADING", "LAZY")
            self.progress.emit(
                5,
                f"Stable Clean · {len(scene_ranges)} scene(s) · LaMa anchors + bidirectional flow",
            )
            self.process = subprocess.Popen(
                command, cwd=str(APP_ROOT), stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                errors="replace", env=environment,
                creationflags=0x08000000 if sys.platform == "win32" else 0,
            )
            lines: list[str] = []
            assert self.process.stdout is not None
            for line in self.process.stdout:
                lines.append(line)
                if len(lines) > 500:
                    lines.pop(0)
                match = re.match(r"FRAME\s+(\d+)\s+(\d+)", line.strip())
                if match:
                    done, total = int(match.group(1)), max(1, int(match.group(2)))
                    percent = 5 + min(90, round(done * 90 / total))
                    self.progress.emit(
                        percent, f"Stable Clean · {done}/{total} frames"
                    )
            self.process.wait()
            if self._cancelled:
                raise RuntimeError("Stable Clean was stopped.")
            if self.process.returncode or not silent_output.is_file():
                raise RuntimeError(
                    f"Stable Clean failed (exit code {self.process.returncode}):\n"
                    + "".join(lines)[-6000:]
                )

            self.progress.emit(97, "Stable Clean · preserving original audio...")
            output = Path(self.temporal_output)
            output.unlink(missing_ok=True)
            final_command = [
                ffmpeg_executable(), "-y", "-hide_banner", "-loglevel", "error",
                "-i", str(silent_output), "-i", self.source,
                "-map", "0:v:0", "-map", "1:a?", "-c:v", codec,
            ]
            if codec in {"h264_nvenc", "hevc_nvenc"}:
                final_command.extend(["-preset", "p4", "-cq", "18"])
            elif codec == "h264_qsv":
                final_command.extend(["-global_quality", "18"])
            elif codec == "h264_amf":
                final_command.extend(["-quality", "quality"])
            final_command.extend([
                "-c:a", "copy", "-movflags", "+faststart", "-shortest", str(output),
            ])
            remux = subprocess.run(
                final_command, capture_output=True,
                creationflags=0x08000000 if sys.platform == "win32" else 0,
            )
            if remux.returncode or not output.is_file():
                details = remux.stderr.decode("utf-8", errors="replace")
                raise RuntimeError("Stable Clean audio mux failed:\n" + details[-3000:])

    def _run_lama_inpaint(self, box: tuple[int, int, int, int], codec: str) -> None:
        import cv2
        import numpy as np
        import torch

        model_path = APP_ROOT / "models" / "lama" / "big-lama.pt"
        if not model_path.is_file():
            raise RuntimeError("The LaMa AI model is missing from models/lama/big-lama.pt.")
        if not torch.cuda.is_available():
            raise RuntimeError("LaMa AI requires a CUDA GPU, but CUDA is unavailable.")
        # LaMa is an independent fallback generated from the original video.
        # Requiring the retired Premium Safe intermediate kept this action locked
        # after the current Stable Clean pipeline completed.
        capture = cv2.VideoCapture(self.source)
        if not capture.isOpened():
            raise RuntimeError("Could not open the original video for LaMa AI.")
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 30.0)
        frame_count = max(1, int(capture.get(cv2.CAP_PROP_FRAME_COUNT)))
        x, y, box_w, box_h = box
        crop_size = min(512, max(256, max(box_w, box_h) * 4))
        cx, cy = x + box_w // 2, y + box_h // 2
        left = max(0, min(width - crop_size, cx - crop_size // 2))
        top = max(0, min(height - crop_size, cy - crop_size // 2))
        right, bottom = min(width, left + crop_size), min(height, top + crop_size)
        crop_w, crop_h = right - left, bottom - top
        target = 256
        mx1 = max(0, round((x - left - 5) * target / crop_w))
        my1 = max(0, round((y - top - 5) * target / crop_h))
        mx2 = min(target, round((x + box_w - left + 5) * target / crop_w))
        my2 = min(target, round((y + box_h - top + 5) * target / crop_h))
        mask_small = np.zeros((target, target), np.float32)
        mask_small[my1:my2, mx1:mx2] = 1.0
        feather_small = cv2.GaussianBlur(mask_small, (0, 0), 2.0)
        feather = cv2.resize(feather_small, (crop_w, crop_h), interpolation=cv2.INTER_LINEAR)[:, :, None]
        device = torch.device("cuda")
        model = torch.jit.load(str(model_path), map_location=device).eval()
        mask_tensor = torch.from_numpy(mask_small[None, None]).to(device)
        command = [
            ffmpeg_executable(), "-y", "-hide_banner", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{width}x{height}",
            "-r", f"{fps:.6f}", "-i", "pipe:0", "-i", self.source,
            "-map", "0:v:0", "-map", "1:a?", "-c:v", codec,
        ]
        if codec in {"h264_nvenc", "hevc_nvenc"}:
            command.extend(["-preset", "p4", "-cq", "18"])
        command.extend(["-c:a", "copy", "-movflags", "+faststart", "-shortest", self.lama_output])
        self.process = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE, creationflags=0x08000000 if sys.platform == "win32" else 0,
        )
        assert self.process.stdin is not None
        processed = 0
        self.progress.emit(80, "LaMa AI · loading the GPU model...")
        with torch.inference_mode():
            while not self._cancelled:
                ok, frame = capture.read()
                if not ok:
                    break
                crop = frame[top:bottom, left:right]
                resized = cv2.resize(crop, (target, target), interpolation=cv2.INTER_AREA)
                rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
                image_tensor = torch.from_numpy(rgb.transpose(2, 0, 1)[None]).to(device)
                result = model(image_tensor, mask_tensor)[0].permute(1, 2, 0)
                result = (result.clamp(0, 1).mul(255).byte().cpu().numpy())
                result = cv2.cvtColor(result, cv2.COLOR_RGB2BGR)
                result = cv2.resize(result, (crop_w, crop_h), interpolation=cv2.INTER_CUBIC)
                blended = crop.astype(np.float32) * (1.0 - feather) + result.astype(np.float32) * feather
                frame[top:bottom, left:right] = np.clip(blended, 0, 255).astype(np.uint8)
                try:
                    self.process.stdin.write(frame.tobytes())
                except BrokenPipeError:
                    break
                processed += 1
                if processed % max(1, round(fps / 2)) == 0:
                    percent = 80 + min(19, round(processed * 20 / frame_count))
                    self.progress.emit(percent, f"LaMa AI GPU · {processed}/{frame_count} frame")
        capture.release()
        try:
            self.process.stdin.close()
        except (BrokenPipeError, OSError):
            pass
        stderr = self.process.stderr.read().decode("utf-8", errors="replace") if self.process.stderr else ""
        self.process.wait()
        del model
        torch.cuda.empty_cache()
        if self._cancelled:
            raise RuntimeError("LaMa AI was stopped.")
        if self.process.returncode or not Path(self.lama_output).is_file():
            raise RuntimeError("LaMa AI rendering failed:\n" + stderr[-4000:])

    def _residual_logo_score(self, box: tuple[int, int, int, int]) -> float:
        import cv2
        import numpy as np

        source_cap = cv2.VideoCapture(self.source)
        clean_cap = cv2.VideoCapture(self.alpha_output)
        total = max(1, int(clean_cap.get(cv2.CAP_PROP_FRAME_COUNT)))
        x, y, width, height = box
        alpha_asset = APP_RUNTIME_ROOT / "assets" / (
            "gemini_bg_96.png" if max(width, height) > 70 else "gemini_bg_48.png"
        )
        template = cv2.imread(str(alpha_asset), cv2.IMREAD_GRAYSCALE)
        if template is None:
            source_cap.release()
            clean_cap.release()
            return 0.0
        template = cv2.resize(template, (width, height), interpolation=cv2.INTER_LINEAR)
        template = template.astype(np.float32).ravel()
        template -= template.mean()
        template_norm = float(np.linalg.norm(template)) + 1e-6

        def correlation(frame) -> float:
            roi = frame[y:y + height, x:x + width]
            if roi.size == 0:
                return 0.0
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY).astype(np.float32)
            local = gray - cv2.GaussianBlur(gray, (0, 0), 5.0)
            values = local.ravel()
            values -= values.mean()
            return max(0.0, float(np.dot(values, template) /
                                  ((np.linalg.norm(values) + 1e-6) * template_norm)))

        ratios = []
        for index in np.linspace(0, total - 1, num=min(5, total), dtype=int):
            source_cap.set(cv2.CAP_PROP_POS_FRAMES, int(index))
            clean_cap.set(cv2.CAP_PROP_POS_FRAMES, int(index))
            ok_source, source_frame = source_cap.read()
            ok_clean, clean_frame = clean_cap.read()
            if ok_source and ok_clean:
                before = correlation(source_frame)
                after = correlation(clean_frame)
                if before > 0.05:
                    ratios.append(min(1.0, after / before))
        source_cap.release()
        clean_cap.release()
        return float(max(ratios, default=0.0))


class AutomationWorker(QObject):
    """Runs one video/audio pair through the four visible production stages."""

    progress = Signal(int, int, str)
    completed = Signal(str)
    failed = Signal(str)
    cancelled = Signal(str)

    def __init__(self, jobs: list[dict], output_dir: Path, voice_config: dict,
                 video_config: dict, caption_config: dict, watermark_config: dict,
                 stage_config: dict | None = None) -> None:
        super().__init__()
        self.jobs = jobs
        self.output_dir = output_dir
        self.voice_config = voice_config
        self.video_config = video_config
        self.caption_config = caption_config
        self.watermark_config = watermark_config
        self.stage_config = stage_config or {
            "voice_clone": True,
            "video_effect": True,
            "caption": True,
            "watermark": True,
        }
        self._cancelled = False
        self.process: subprocess.Popen | None = None
        self.child_worker: QObject | None = None
        self.last_caption_timing_scale = 1.0
        self.job_input_lock = threading.Lock()
        self.caption_model_instance = None
        self.caption_model_key: tuple[str, str] | None = None

    def update_job_trailer(self, table_row: int, trailer_path: str) -> None:
        with self.job_input_lock:
            for job in self.jobs:
                if job.get("_table_row") == table_row:
                    job["trailer"] = trailer_path.strip()

    def update_job_channels(self, table_row: int, channel_names: str) -> None:
        with self.job_input_lock:
            for job in self.jobs:
                if job.get("_table_row") == table_row:
                    job["channels"] = channel_names.strip()

    def current_job_trailer(self, job: dict) -> str:
        with self.job_input_lock:
            return str(job.get("trailer", "")).strip()

    def current_job_channels(self, job: dict) -> str:
        with self.job_input_lock:
            return str(job.get("channels", "")).strip()

    def cancel(self) -> None:
        self._cancelled = True
        if self.process and self.process.poll() is None:
            self.process.terminate()
        if self.child_worker and hasattr(self.child_worker, "request_cancel"):
            self.child_worker.request_cancel()

    def run_command(
        self,
        command: list[str],
        progress_label: str = "",
        current: int = 0,
        total: int = 0,
        duration_seconds: float = 0.0,
    ) -> None:
        started = time.monotonic()
        self.process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=0x08000000 if sys.platform == "win32" else 0,
        )
        output_lines: list[str] = []
        last_bucket = -1
        emitted_completion = False
        assert self.process.stdout is not None
        for line in self.process.stdout:
            if self._cancelled:
                self.process.terminate()
                raise InterruptedError
            output_lines.append(line)
            if len(output_lines) > 500:
                output_lines.pop(0)
            stripped = line.strip()
            if not progress_label:
                continue
            now = time.monotonic()
            rendered = None
            if stripped.startswith(("out_time_ms=", "out_time_us=")):
                try:
                    rendered = int(stripped.split("=", 1)[1]) / 1_000_000
                except ValueError:
                    rendered = None
            elif stripped.startswith("out_time="):
                try:
                    parts = stripped.split("=", 1)[1].split(":")
                    rendered = int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
                except Exception:
                    rendered = None
            fraction = min(1.0, max(0.0, (rendered or 0.0) / duration_seconds)) if duration_seconds > 0 else 0.0
            if duration_seconds > 0:
                bucket = min(10, int(fraction * 10))
                if bucket <= last_bucket and fraction < 1.0:
                    continue
                if bucket == 0 and last_bucket >= 0:
                    continue
                last_bucket = bucket
            elif rendered is None:
                continue
            elapsed = now - started
            eta = elapsed * (1 - fraction) / fraction if fraction > 0 else 0
            if duration_seconds > 0:
                percent = min(100, bucket * 10)
                progress_current = current * 100 + percent
                progress_total = max(1, total * 100)
                percent_text = f"{percent}%"
                emitted_completion = percent >= 100
            else:
                progress_current = current
                progress_total = total
                percent_text = "đang xử lý"
            eta_text = f" · ETA {self.format_duration(eta)}" if eta else ""
            self.progress.emit(
                progress_current,
                progress_total,
                f"{progress_label} · {percent_text} · elapsed {self.format_duration(elapsed)}{eta_text}",
            )
        self.process.wait()
        if self._cancelled:
            raise InterruptedError
        output = "".join(output_lines)
        if self.process.returncode:
            raise RuntimeError(output[-5000:])
        if progress_label and not emitted_completion:
            self.progress.emit(
                current * 100 + 100 if duration_seconds > 0 else current,
                max(1, total * 100) if duration_seconds > 0 else total,
                f"{progress_label} · 100% · elapsed {self.format_duration(time.monotonic() - started)}",
            )

    @staticmethod
    def srt_timestamp(seconds: float) -> str:
        milliseconds = max(0, round(seconds * 1000))
        hours, milliseconds = divmod(milliseconds, 3_600_000)
        minutes, milliseconds = divmod(milliseconds, 60_000)
        secs, milliseconds = divmod(milliseconds, 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"

    def transcribe_sidecar(self, media: Path, destination: Path) -> Path:
        from faster_whisper import WhisperModel

        options = self.caption_config.get("transcribe", {})
        requested_device = str(options.get("device", "Auto")).lower()
        device = "cpu"
        if requested_device != "cpu":
            try:
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
            except Exception:
                pass
        model_name = str(options.get("model", "small")).strip().lower().replace(" ", "-")
        language = str(options.get("language", "Auto")).strip().lower()
        language = None if language in ("", "auto", "auto detect") else language[:2]
        model = WhisperModel(
            model_name, device=device, compute_type="float16" if device == "cuda" else "int8"
        )
        segments, _ = model.transcribe(
            str(media), language=language, vad_filter=bool(options.get("vad_filter", True))
        )
        blocks = []
        for index, segment in enumerate(segments, 1):
            blocks.append(
                f"{index}\n{self.srt_timestamp(segment.start)} --> "
                f"{self.srt_timestamp(segment.end)}\n{segment.text.strip()}\n"
            )
        destination.write_text("\n".join(blocks), encoding="utf-8")
        return destination

    @staticmethod
    def format_ass_timestamp(seconds: float) -> str:
        centis = round(max(0.0, seconds) * 100)
        hours, rem = divmod(centis, 360000)
        minutes, rem = divmod(rem, 6000)
        secs, cs = divmod(rem, 100)
        return f"{hours}:{minutes:02d}:{secs:02d}.{cs:02d}"

    @staticmethod
    def clean_hex(value: str, fallback: str) -> str:
        value = str(value).strip().upper()
        if re.fullmatch(r"#[0-9A-F]{6}", value):
            return value
        return fallback

    def ass_color(self, hex_color: str) -> str:
        value = self.clean_hex(hex_color, "#FFFFFF")
        return f"&H00{value[5:7]}{value[3:5]}{value[1:3]}"

    def ass_override_color(self, hex_color: str) -> str:
        value = self.clean_hex(hex_color, "#FFFFFF")
        return f"&H{value[5:7]}{value[3:5]}{value[1:3]}&"

    @staticmethod
    def ass_escape(text: str) -> str:
        return str(text).replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", "\\N")

    def ass_dialogue_line(self, start: float, end: float, text: str) -> str:
        return (
            f"Dialogue: 0,{self.format_ass_timestamp(start)},{self.format_ass_timestamp(end)},"
            f"Default,,0,0,0,,{text}\n"
        )

    @staticmethod
    def caption_words_with_timing(segment: dict) -> list[dict]:
        segment_start = float(segment.get("start", 0.0))
        segment_end = max(segment_start + 0.01, float(segment.get("end", segment_start + 0.01)))
        raw_words = sorted(
            (
                word for word in segment.get("words", [])
                if word.get("text")
            ),
            key=lambda word: (float(word.get("start", segment_start)), float(word.get("end", segment_end))),
        )
        if raw_words:
            normalized = []
            cursor = segment_start
            for word in raw_words:
                text = str(word.get("text", "")).strip()
                if not text:
                    continue
                start = max(segment_start, cursor, float(word.get("start", cursor)))
                end = min(segment_end, float(word.get("end", start + 0.05)))
                if end <= start:
                    end = min(segment_end, start + 0.05)
                if end <= start:
                    continue
                normalized.append({"text": text, "start": start, "end": end})
                cursor = end
            if normalized:
                return normalized
        tokens = str(segment.get("text", "")).split()
        if not tokens:
            return []
        start = segment_start
        duration = max(0.01, segment_end - start)
        weights = [max(1, len(token.strip(".,!?;:"))) for token in tokens]
        total_weight = sum(weights)
        cursor = start
        result = []
        for index, (token, weight) in enumerate(zip(tokens, weights)):
            end = float(segment["end"]) if index == len(tokens) - 1 else cursor + duration * weight / total_weight
            result.append({"text": token, "start": cursor, "end": end})
            cursor = end
        return result

    def group_caption_segments(self, segments: list[dict]) -> list[dict]:
        max_words = max(1, int(self.caption_config["layout"].get("max_words_per_line", 6)))
        grouped = []
        for segment in segments:
            words = self.caption_words_with_timing(segment)
            if not words:
                continue
            for start_index in range(0, len(words), max_words):
                chunk = words[start_index:start_index + max_words]
                grouped.append(
                    {
                        "start": float(chunk[0]["start"]),
                        "end": float(chunk[-1]["end"]),
                        "text": " ".join(str(word["text"]).strip() for word in chunk).strip(),
                        "words": chunk,
                    }
                )
        return grouped

    def segments_to_ass(self, segments: list[dict]) -> str:
        config = self.caption_config
        style = config["style"]
        layout = config["layout"]
        alignment = {"Left": 1, "Center": 2, "Right": 3}.get(layout["alignment"], 2)
        alignment += {"Bottom": 0, "Middle": 3, "Top": 6}.get(layout["anchor"], 0)
        primary = self.ass_color(style["base_color"])
        secondary = self.ass_color(style["active_color"])
        outline = self.ass_color(style["outline_color"])
        back = self.ass_color(style["shadow_color"])
        bold = -1 if style["bold"] else 0
        italic = -1 if style["italic"] else 0
        line_box = style["background_mode"] == "Line box"
        border_style = 3 if line_box else 1
        style_outline = self.ass_color(style["background_color"]) if line_box else outline
        style_outline_width = max(style["padding_x"], style["padding_y"]) if line_box else style["outline_width"]
        header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{style['font_family']},{style['font_size']},{primary},{secondary},{style_outline},{back},{bold},{italic},0,0,100,100,{style['letter_spacing']},0,{border_style},{style_outline_width},2,{alignment},{layout['margin_x']},{layout['margin_x']},{layout['margin_bottom']},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        lines = [header]
        for segment in segments:
            words = self.caption_words_with_timing(segment)
            highlight_type = style["highlight_type"]
            if highlight_type == "None" or not words:
                text = self.ass_escape(segment["text"])
                if style["uppercase"]:
                    text = text.upper()
                lines.append(self.ass_dialogue_line(segment["start"], segment["end"], text))
                continue
            if highlight_type == "Progressive sweep":
                karaoke_parts = []
                for word in words:
                    duration_cs = max(1, round((word["end"] - word["start"]) * 100))
                    text = word["text"].upper() if style["uppercase"] else word["text"]
                    karaoke_parts.append(f"{{\\kf{duration_cs}}}{self.ass_escape(text)}")
                lines.append(self.ass_dialogue_line(segment["start"], segment["end"], " ".join(karaoke_parts)))
                continue
            event_cursor = float(segment["start"])
            segment_end = max(event_cursor + 0.01, float(segment["end"]))
            for active_index, word in enumerate(words):
                rendered_words = []
                for index, item in enumerate(words):
                    text = item["text"].upper() if style["uppercase"] else item["text"]
                    escaped = self.ass_escape(text)
                    if index == active_index:
                        if highlight_type == "Active background" or style["background_mode"] == "Active word box":
                            background = self.ass_override_color(style["background_color"])
                            escaped = (
                                f"{{\\1c{self.ass_override_color(style['active_color'])}"
                                f"\\3c{background}\\bord{max(6, style['padding_y'])}}}"
                                f"{escaped}{{\\r}}"
                            )
                        else:
                            escaped = f"{{\\1c{self.ass_override_color(style['active_color'])}}}{escaped}{{\\r}}"
                    rendered_words.append(escaped)
                event_start = max(event_cursor, float(segment["start"]) if active_index == 0 else float(word["start"]))
                event_end = (
                    float(words[active_index + 1]["start"])
                    if active_index + 1 < len(words)
                    else segment_end
                )
                event_end = min(segment_end, max(event_start + 0.01, event_end))
                if event_start >= segment_end:
                    continue
                lines.append(
                    self.ass_dialogue_line(
                        event_start,
                        event_end,
                        " ".join(rendered_words),
                    )
                )
                event_cursor = event_end
        return "".join(lines)

    def transcribe_ass_sidecar(self, media: Path, destination: Path) -> Path:
        from faster_whisper import WhisperModel

        options = self.caption_config.get("transcribe", {})
        requested_device = str(options.get("device", "Auto")).lower()
        device = "cpu"
        if requested_device != "cpu":
            try:
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
            except Exception:
                pass
        model_name = str(options.get("model", "small")).strip().lower().replace(" ", "-")
        language = str(options.get("language", "Auto")).strip().lower()
        language = None if language in ("", "auto", "auto detect") else language[:2]
        model_key = (model_name, device)
        if self.caption_model_instance is None or self.caption_model_key != model_key:
            self.caption_model_instance = WhisperModel(
                model_name,
                device=device,
                compute_type="float16" if device == "cuda" else "int8",
            )
            self.caption_model_key = model_key
        raw_segments, _ = self.caption_model_instance.transcribe(
            str(media),
            language=language,
            vad_filter=bool(options.get("vad_filter", True)),
            word_timestamps=bool(options.get("word_timing", True)),
        )
        segments = []
        for raw in raw_segments:
            words = [
                {
                    "text": word.word.strip(),
                    "start": float(word.start),
                    "end": float(word.end),
                }
                for word in (raw.words or [])
                if word.word.strip()
            ]
            text = str(raw.text).strip()
            if text:
                segments.append({"start": float(raw.start), "end": float(raw.end), "text": text, "words": words})
        media_duration = media_duration_seconds(str(media))
        segments, timing_scale = align_caption_segments_to_media_duration(
            segments, media_duration
        )
        self.last_caption_timing_scale = timing_scale
        if timing_scale < 1.0:
            log_event(
                "CAPTION | corrected accumulated audio clock drift | "
                f"decoded/media ratio={1.0 / timing_scale:.6f}"
            )
        destination.write_text(self.segments_to_ass(self.group_caption_segments(segments)), encoding="utf-8")
        return destination

    def prepare_caption_sidecar(self, current: Path, script: Path | None, job_dir: Path,
                                total: int, done: int) -> Path:
        sidecar = next((p for p in (
            current.with_suffix(".ass"), current.with_suffix(".srt"),
            script.with_suffix(".ass") if script else Path(),
            script.with_suffix(".srt") if script else Path(),
        ) if p.is_file()), None)
        if sidecar is not None:
            return sidecar
        cached_ass = job_dir / "03_caption.ass"
        cache_metadata = job_dir / "03_caption.cache.json"
        source_stat = current.stat()
        expected_cache = {
            "version": 2,
            "source": str(current.resolve()),
            "source_size": source_stat.st_size,
            "source_mtime_ns": source_stat.st_mtime_ns,
            "caption_config": self.caption_config,
        }
        if cached_ass.is_file() and cache_metadata.is_file():
            try:
                saved_cache = json.loads(cache_metadata.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                saved_cache = {}
            if saved_cache == expected_cache:
                self.progress.emit(
                    done, total, f"Caption dùng lại ASS cache: {cached_ass}"
                )
                return cached_ass
        self.progress.emit(done, total, "Đang tự nhận diện lời thoại theo cấu hình Caption...")
        result = self.transcribe_ass_sidecar(current, cached_ass)
        cache_metadata.write_text(
            json.dumps(expected_cache, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if self.last_caption_timing_scale < 1.0:
            self.progress.emit(
                done,
                total,
                "Caption đã sửa drift tích lũy theo duration video "
                f"(hệ số {self.last_caption_timing_scale:.6f}).",
            )
        return result

    @staticmethod
    def newest_file(paths: list[Path]) -> Path | None:
        existing = [path for path in paths if path.is_file()]
        if not existing:
            return None
        return max(existing, key=lambda path: path.stat().st_mtime)

    @staticmethod
    def channel_names(raw: str) -> list[str]:
        names = [line.strip() for line in raw.splitlines() if line.strip()]
        return names or ["Channel"]

    @staticmethod
    def safe_filename(value: str) -> str:
        return re.sub(r'[<>:"/\\|?*]+', "_", value).strip(" .") or "output"

    @staticmethod
    def format_duration(seconds: float) -> str:
        total_seconds = max(0, round(seconds))
        if total_seconds < 60:
            return f"{total_seconds}s"
        minutes, remaining_seconds = divmod(total_seconds, 60)
        return f"{minutes:02d}:{remaining_seconds:02d}"

    def timing_report(
        self,
        number: int,
        safe: str,
        stage_times: dict[str, float],
        job_stages: dict,
        job_elapsed: float,
    ) -> str:
        stage_keys = (
            ("Voice Clone", "voice_clone"),
            ("Video Effect", "video_effect"),
            ("Caption", "caption"),
            ("Watermark", "watermark"),
        )
        lines = [
            f"=== TIME STATISTICS · VIDEO {number}/{len(self.jobs)} · {safe} ==="
        ]
        for stage_name, stage_key in stage_keys:
            value = (
                self.format_duration(stage_times.get(stage_name, 0.0))
                if job_stages.get(stage_key, True)
                else "SKIPPED"
            )
            lines.append(f"{stage_name}: {value}")
        lines.append(f"TOTAL VIDEO: {self.format_duration(job_elapsed)}")
        lines.append("===============================================")
        return "\n".join(lines)

    def run_voice_clone_stage(self, script: Path, output_dir: Path, total: int, done: int) -> Path:
        config = self.voice_config
        started = time.monotonic()
        engine = str(config.get("engine", "original"))
        if engine == "v3":
            worker = ChatterboxRenderWorker(
                config["profile"], script, output_dir,
                config["language"], config["device_mode"], config["output_format"],
                config["exaggeration"], config["cfg_weight"], config["temperature"],
                config["repetition_penalty"], config["min_p"], config["top_p"],
                config["auto_qa"], config["qa_retries"], config["asr_workers"],
                False, None, config["normalize_audio"],
            )
            engine_label = "Voice Clone v3"
        else:
            worker = RenderWorker(
                config["profile"],
                script,
                output_dir,
                config["model_name"],
                config["steps"],
                config["fit_timeline"],
                config["output_format"],
                None,
                config["device_mode"],
                config["cooldown_seconds"],
                config["reload_every"],
                1,
                None,
                False,
                config["normalize_audio"],
                config["language"],
                config["speaking_style"],
                config["auto_style"],
                {},
                output_suffix="",
            )
            engine_label = "Voice Clone (Original)"
        errors: list[str] = []
        completed: list[str] = []
        cancelled: list[str] = []
        worker.progress.connect(
            lambda _current, _count, text: self.progress.emit(
                done,
                total,
                f"{engine_label} · elapsed {self.format_duration(time.monotonic() - started)} · {text}",
            )
        )
        worker.completed.connect(lambda path: completed.append(path))
        worker.cancelled.connect(lambda message: cancelled.append(message))
        worker.failed.connect(lambda details: errors.append(details))
        self.child_worker = worker
        worker.run()
        self.child_worker = None
        if self._cancelled or cancelled:
            raise InterruptedError
        if errors:
            raise RuntimeError(errors[-1])
        if not completed:
            raise RuntimeError(f"{engine_label} did not produce an output folder.")
        self.progress.emit(
            done,
            total,
            f"{engine_label} hoàn tất trong {self.format_duration(time.monotonic() - started)}: {completed[-1]}",
        )
        return Path(completed[-1])

    def run_video_effect_stage(self, images_dir: Path, audios_dir: Path, output_dir: Path,
                               total: int, done: int) -> Path:
        config = self.video_config
        started = time.monotonic()
        if not images_dir.is_dir():
            raise RuntimeError(f"Images folder does not exist: {images_dir}")
        if not audios_dir.is_dir():
            raise RuntimeError(f"Audio folder does not exist: {audios_dir}")
        image_count = sum(
            1 for path in images_dir.iterdir()
            if path.is_file() and path.suffix.lower() in VIDEO_IMAGE_EXTS
        )
        audio_count = sum(
            1 for path in audios_dir.iterdir()
            if path.is_file() and path.suffix.lower() in VIDEO_AUDIO_EXTS
        )
        if image_count == 0 or audio_count == 0:
            raise RuntimeError(
                "Video Effect cannot start because no supported media pair was found.\n"
                f"Images: {image_count} file(s) in {images_dir}\n"
                f"Audio: {audio_count} file(s) in {audios_dir}"
            )
        if image_count != audio_count:
            raise RuntimeError(
                "Video Effect requires the same number of images and audio files.\n"
                f"Images: {image_count} file(s) in {images_dir}\n"
                f"Audio: {audio_count} file(s) in {audios_dir}"
            )
        worker = VideoEffectWorker(
            VIDEO_EFFECT_SCRIPT,
            images_dir,
            audios_dir,
            output_dir,
            config["width"],
            config["height"],
            config["fps"],
            config["crf"],
            config["codec"],
            config["workers"],
            config["pattern"],
            config["random_effects"],
            config["bounce"],
            config["zoom_scale"],
            config["base_crop"],
            config["edge_reach"],
            config["face_safe"],
            config["speed"],
            config["pre_silence"],
            config["min_motion"],
            config["combo_radius"],
            config["combo_offset_x"],
            config["combo_offset_y"],
            config["retro_preset"],
            config["retro_scratches_enabled"],
            config["retro_scratch"],
            config["retro_dust_enabled"],
            config["retro_dust"],
            config["retro_grain_enabled"],
            config["retro_grain"],
            config["retro_flicker_enabled"],
            config["retro_flicker"],
            config["retro_vignette_enabled"],
            config["retro_vignette"],
            config["retro_color_fade_enabled"],
            config["retro_color_fade"],
            config["retro_scan_lines_enabled"],
            config["retro_scan_lines"],
            config["merge_videos"],
        )
        errors: list[str] = []
        completed: list[str] = []
        cancelled: list[str] = []
        worker.progress.connect(
            lambda text: self.progress.emit(
                done,
                total,
                f"Video Effect · elapsed {self.format_duration(time.monotonic() - started)} · {text}",
            )
        )
        worker.segment_progress.connect(
            lambda current, count, filename: self.progress.emit(
                done,
                total,
                f"Video Effect · elapsed {self.format_duration(time.monotonic() - started)} · {current}/{count}: {filename}",
            )
        )
        worker.completed.connect(lambda path: completed.append(path))
        worker.cancelled.connect(lambda message: cancelled.append(message))
        worker.failed.connect(lambda details: errors.append(details))
        self.child_worker = worker
        worker.run()
        self.child_worker = None
        if self._cancelled or cancelled:
            raise InterruptedError
        if errors:
            raise RuntimeError(errors[-1])
        output_root = Path(completed[-1]) if completed else output_dir
        candidates = [output_root / "final_merged.mp4"]
        merged_dir = output_root / "merged"
        if merged_dir.is_dir():
            candidates.extend(sorted(merged_dir.glob("*.mp4")))
        candidates.extend(sorted(output_root.glob("*.mp4")))
        candidates.extend(sorted(output_root.rglob("*.mp4")))
        result = self.newest_file(candidates)
        if result is None:
            raise RuntimeError(f"Video Effect completed but no MP4 output was found in {output_root}")
        self.progress.emit(
            done,
            total,
            f"Video Effect hoàn tất trong {self.format_duration(time.monotonic() - started)}: {result}",
        )
        return result

    def run(self) -> None:
        try:
            batch_started = time.monotonic()
            self.output_dir.mkdir(parents=True, exist_ok=True)
            total = len(self.jobs) * 4
            done = 0
            for number, job in enumerate(self.jobs, 1):
                if self._cancelled:
                    raise InterruptedError
                script = Path(job["script"]) if job.get("script") else None
                images = Path(job["images"]) if job.get("images") else None
                audios = Path(job["audios"]) if job.get("audios") else None
                video = Path(job["video"]) if job.get("video") else None
                source_name = script or images or video or Path(f"job_{number}")
                safe = self.safe_filename(source_name.stem if source_name.suffix else source_name.name) or f"job_{number}"
                job_output = Path(job.get("output") or self.output_dir)
                job_dir = job_output / f"{number:03d}_{safe}"
                job_dir.mkdir(parents=True, exist_ok=True)
                job_started = time.monotonic()
                stage_times: dict[str, float] = {}
                job_stages = job.get("stages") or self.stage_config
                self.progress.emit(done, total, f"=== Bắt đầu file {number}/{len(self.jobs)}: {safe} ===")
                self.progress.emit(
                    done,
                    total,
                    f"Group name: {job.get('batch_group', AUTOMATION_BATCH_GROUPS[0])} · "
                    f"Processing group: {job.get('processing_group', 'Pipeline mặc định')}",
                )

                current = video

                voice_out = job_dir / "01_voice_clone.mp4"
                stage_started = time.monotonic()
                if job_stages.get("voice_clone", True):
                    if script is None:
                        raise ValueError(f"Job {number}: Voice Clone đang bật nên cần file .txt/.str.")
                    self.progress.emit(done, total, f"{number}/{len(self.jobs)} · Voice Clone · đang xử lý...")
                    audios = self.run_voice_clone_stage(script, job_dir / "01_voice_clone_audio", total, done)
                    message = f"Voice Clone xong trong {self.format_duration(time.monotonic() - stage_started)}: {audios}"
                else:
                    message = (
                        "Bỏ qua Voice Clone · dùng audio folder/video input có sẵn · "
                        f"{self.format_duration(time.monotonic() - stage_started)}"
                    )
                stage_times["Voice Clone"] = time.monotonic() - stage_started
                done += 1
                self.progress.emit(done, total, message)

                effect_out = job_dir / "02_video_effect.mp4"
                stage_started = time.monotonic()
                if job_stages.get("video_effect", True):
                    if images is None or audios is None:
                        raise ValueError(f"Job {number}: Video Effect đang bật nên cần Images folder và Audio folder.")
                    generated_audio_count = sum(
                        1 for path in audios.iterdir()
                        if path.is_file() and path.suffix.lower() in VIDEO_AUDIO_EXTS
                    ) if audios.is_dir() else 0
                    audio_origin = (
                        "output vừa tạo từ Voice Clone"
                        if job_stages.get("voice_clone", True)
                        else "Audio folder của input"
                    )
                    self.progress.emit(
                        done,
                        total,
                        f"{number}/{len(self.jobs)} · Video Effect nhận {audio_origin}: "
                        f"{audios} · {generated_audio_count} audio file(s)",
                    )
                    self.progress.emit(done, total, f"{number}/{len(self.jobs)} · Video Effect · đang xử lý...")
                    current = self.run_video_effect_stage(images, audios, job_dir / "02_video_effect", total, done)
                    message = f"Video Effect xong trong {self.format_duration(time.monotonic() - stage_started)}: {current}"
                else:
                    message = (
                        "Bỏ qua Video Effect · chuyển output trước sang Caption · "
                        f"{self.format_duration(time.monotonic() - stage_started)}"
                    )
                stage_times["Video Effect"] = time.monotonic() - stage_started
                done += 1
                self.progress.emit(done, total, message)

                caption_out = job_dir / "03_caption.mp4"
                combine_caption_watermark = (
                    job_stages.get("caption", True)
                    and job_stages.get("watermark", True)
                    and self.caption_config.get("export", {}).get("burn_video", True)
                )
                combined_caption_sidecar: Path | None = None
                stage_started = time.monotonic()
                if combine_caption_watermark:
                    if current is None:
                        raise ValueError(f"Job {number}: Caption đang bật nhưng chưa có video input.")
                    self.progress.emit(done, total, f"{number}/{len(self.jobs)} · Caption · chuẩn bị để gộp Watermark...")
                    combined_caption_sidecar = self.prepare_caption_sidecar(current, script, job_dir, total, done)
                    message = (
                        f"Caption chuẩn bị xong trong {self.format_duration(time.monotonic() - stage_started)} "
                        f"để gộp với Watermark: {combined_caption_sidecar}"
                    )
                elif job_stages.get("caption", True):
                    if current is None:
                        raise ValueError(f"Job {number}: Caption đang bật nhưng chưa có video input.")
                    self.progress.emit(done, total, f"{number}/{len(self.jobs)} · Caption · đang render...")
                    sidecar = self.prepare_caption_sidecar(current, script, job_dir, total, done)
                    if sidecar and self.caption_config.get("export", {}).get("burn_video", True):
                        codec = require_video_gpu_codec()
                        self.run_command([
                            ffmpeg_executable(), "-y", "-i", str(current),
                            "-vf", f"subtitles={ffmpeg_filter_path(sidecar)}",
                            "-c:v", codec, "-c:a", "copy", "-movflags", "+faststart",
                            "-progress", "pipe:1", "-nostats", str(caption_out),
                        ], f"Caption render file {number}/{len(self.jobs)}", done, total, media_duration_seconds(str(current)))
                    else:
                        shutil.copy2(current, caption_out)
                    current = caption_out
                    message = f"Caption xong trong {self.format_duration(time.monotonic() - stage_started)}: {caption_out}"
                else:
                    message = (
                        "Bỏ qua Caption · chuyển output trước sang Watermark · "
                        f"{self.format_duration(time.monotonic() - stage_started)}"
                    )
                stage_times["Caption"] = time.monotonic() - stage_started
                done += 1
                self.progress.emit(done, total, message)

                source_stem = self.safe_filename(source_name.stem if source_name.suffix else source_name.name)
                final_out = job_dir / f"04_final_{source_stem}.mp4"
                stage_started = time.monotonic()
                if job_stages.get("watermark", True):
                    if current is None:
                        raise ValueError(f"Job {number}: Watermark đang bật nhưng chưa có video input.")
                    self.progress.emit(done, total, f"{number}/{len(self.jobs)} · Watermark · đang render...")
                    wm = dict(self.watermark_config)
                    wm["warning"] = dict(wm["warning"])
                    wm["subscribe"] = dict(wm["subscribe"])
                    wm["trailer"] = dict(wm.get("trailer", {}))
                    latest_trailer = self.current_job_trailer(job)
                    if job_stages.get("channel_only", False):
                        wm["trailer"]["video"] = ""
                    elif latest_trailer and Path(latest_trailer).is_file():
                        wm["trailer"]["video"] = latest_trailer
                        self.progress.emit(
                            done,
                            total,
                            f"Watermark nhận Trailer video mới nhất: {latest_trailer}",
                        )
                    else:
                        wm["trailer"]["video"] = ""
                        self.progress.emit(
                            done,
                            total,
                            "Watermark kiểm tra Trailer: chưa có file hợp lệ, bỏ qua Trailer.",
                        )
                    outputs = []
                    latest_channels = self.current_job_channels(job)
                    names = [
                        line.strip()
                        for line in latest_channels.splitlines()
                        if line.strip()
                    ]
                    if names:
                        self.progress.emit(
                            done,
                            total,
                            f"Watermark nhận {len(names)} Channel Name mới nhất: "
                            + ", ".join(names),
                        )
                    else:
                        self.progress.emit(
                            done,
                            total,
                            "Watermark kiểm tra Channel Name: chưa chọn kênh, "
                            "bỏ qua overlay tên kênh.",
                        )
                    if job_stages.get("channel_only", False):
                        if not names:
                            output = job_dir / f"04_final_{source_stem}_no_channel.mp4"
                            shutil.copy2(current, output)
                            outputs.append(output)
                            message = (
                                "Channel-only không có Channel Name tại thời điểm xử lý; "
                                f"đã giữ nguyên base: {output}"
                            )
                            stage_times["Watermark"] = time.monotonic() - stage_started
                            done += 1
                            self.progress.emit(done, total, message)
                            job_elapsed = time.monotonic() - job_started
                            self.progress.emit(
                                done,
                                total,
                                self.timing_report(
                                    number, safe, stage_times, job_stages, job_elapsed
                                ),
                            )
                            self.progress.emit(
                                done,
                                total,
                                f"=== Hoàn tất file {number}/{len(self.jobs)} trong "
                                f"{self.format_duration(job_elapsed)}: {job_dir} ===",
                            )
                            continue
                        channel_wm = dict(wm)
                        channel_wm["trailer"] = {"video": "", "transition": 0.0}
                        channel_wm["warning"] = {
                            "image": "", "duration": 0.0, "fit": "Crop"
                        }
                        channel_wm["subscribe"] = {
                            "video": "", "start": 0.0, "duration": None,
                            "interval": 1.0, "count": 1,
                            "position": "Bottom Right", "scale": 30,
                            "chroma_key": False, "chroma_color": "#00FF00",
                            "similarity": 0.2, "blend": 0.08,
                        }
                        base_duration = media_duration_seconds(str(current))
                        variants = []
                        for channel_index, channel_name in enumerate(names, 1):
                            output = job_dir / (
                                f"04_final_{source_stem}_{channel_index:02d}_"
                                f"{self.safe_filename(channel_name)}.mp4"
                            )
                            variants.append({
                                "name": channel_name,
                                "output": str(output),
                                "overlay": str(create_channel_name_overlay_image(
                                    channel_name,
                                    channel_wm,
                                    job_dir / "_watermark_assets",
                                    output.stem + "_channel",
                                )),
                            })
                            outputs.append(output)
                        max_parallel_outputs = 3
                        groups = [
                            variants[index:index + max_parallel_outputs]
                            for index in range(0, len(variants), max_parallel_outputs)
                        ]
                        for group_index, group in enumerate(groups, 1):
                            self.run_command(
                                build_watermark_ffmpeg_command({
                                    "input": str(current),
                                    "output": group[0]["output"],
                                    "channel_variants": group,
                                    "caption": "",
                                    "logo": "",
                                }, channel_wm),
                                f"Channel-only multi-output group {group_index}/{len(groups)} "
                                f"({len(group)} channels) "
                                f"file {number}/{len(self.jobs)}",
                                done,
                                total,
                                base_duration,
                            )
                    elif len(names) > 1:
                        watermark_duration = media_duration_seconds(str(current))
                        trailer_video = str(wm.get("trailer", {}).get("video", "")).strip()
                        if trailer_video:
                            watermark_duration += media_duration_seconds(trailer_video)
                        variants = []
                        for channel_index, channel_name in enumerate(names, 1):
                            output = job_dir / (
                                f"04_final_{source_stem}_{channel_index:02d}_"
                                f"{self.safe_filename(channel_name)}.mp4"
                            )
                            variants.append({
                                "name": channel_name,
                                "output": str(output),
                                "overlay": str(create_channel_name_overlay_image(
                                    channel_name,
                                    wm,
                                    job_dir / "_watermark_assets",
                                    output.stem + "_channel",
                                )),
                            })
                            outputs.append(output)
                        max_parallel_outputs = 3
                        groups = [
                            variants[index:index + max_parallel_outputs]
                            for index in range(0, len(variants), max_parallel_outputs)
                        ]
                        for group_index, group in enumerate(groups, 1):
                            self.run_command(
                                build_watermark_ffmpeg_command({
                                    "input": str(current),
                                    "output": group[0]["output"],
                                    "logo": job.get("logo", ""),
                                    "caption": (
                                        str(combined_caption_sidecar)
                                        if combined_caption_sidecar else ""
                                    ),
                                    "channel_variants": group,
                                }, wm),
                                f"Watermark multi-output group {group_index}/{len(groups)} "
                                f"({len(group)} channels) file {number}/{len(self.jobs)}",
                                done,
                                total,
                                watermark_duration,
                            )
                    else:
                        channel_name = names[0] if names else ""
                        watermark_duration = media_duration_seconds(str(current))
                        trailer_video = str(wm.get("trailer", {}).get("video", "")).strip()
                        if trailer_video:
                            watermark_duration += media_duration_seconds(trailer_video)
                        self.run_command(build_watermark_ffmpeg_command({
                            "input": str(current), "name": channel_name, "output": str(final_out),
                            "logo": job.get("logo", ""),
                            "caption": str(combined_caption_sidecar) if combined_caption_sidecar else "",
                        }, wm), f"Watermark render file {number}/{len(self.jobs)}", done, total, watermark_duration)
                        outputs.append(final_out)
                    message = (
                        f"Watermark xong trong {self.format_duration(time.monotonic() - stage_started)} · "
                        + "outputs: "
                        + ", ".join(str(path) for path in outputs)
                    )
                else:
                    if current is None:
                        message = (
                            "Bỏ qua Watermark · pipeline hiện chỉ có audio output, không tạo final video · "
                            f"{self.format_duration(time.monotonic() - stage_started)}"
                        )
                    else:
                        shutil.copy2(current, final_out)
                        message = (
                            f"Bỏ qua Watermark · lưu video cuối trong "
                            f"{self.format_duration(time.monotonic() - stage_started)}: {final_out}"
                        )
                stage_times["Watermark"] = time.monotonic() - stage_started
                done += 1
                self.progress.emit(done, total, message)
                job_elapsed = time.monotonic() - job_started
                self.progress.emit(
                    done,
                    total,
                    self.timing_report(
                        number, safe, stage_times, job_stages, job_elapsed
                    ),
                )
                self.progress.emit(
                    done,
                    total,
                    f"=== Hoàn tất file {number}/{len(self.jobs)} trong "
                    f"{self.format_duration(job_elapsed)}: {job_dir} ===",
                )
            self.progress.emit(
                done,
                total,
                f"Automation batch hoàn tất trong {self.format_duration(time.monotonic() - batch_started)}",
            )
            self.completed.emit(str(self.output_dir))
        except InterruptedError:
            self.cancelled.emit("Automation đã dừng. Các video hoàn tất trước đó vẫn được giữ lại.")
        except Exception:
            self.failed.emit(traceback.format_exc())


def ffmpeg_escape_drawtext(value: str) -> str:
    return value.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace("%", "\\%")


def ffmpeg_filter_path(path: Path) -> str:
    value = str(path.resolve()).replace("\\", "/").replace(":", "\\:")
    return "'" + value.replace("'", "\\'") + "'"


def watermark_xy(position: str, padding_x: int, padding_y: int, overlay: bool = False) -> tuple[str, str]:
    width = "overlay_w" if overlay else "text_w"
    height = "overlay_h" if overlay else "text_h"
    x = str(padding_x) if "Left" in position else f"main_w-{width}-{padding_x}"
    y = str(padding_y) if "Top" in position else f"main_h-{height}-{padding_y}"
    return x, y


def watermark_text_xy(position: str, padding_x: int, padding_y: int, box_padding: int) -> tuple[str, str]:
    x = str(padding_x + box_padding) if "Left" in position else f"main_w-text_w-{padding_x + box_padding}"
    y = str(padding_y + box_padding) if "Top" in position else f"main_h-text_h-{padding_y + box_padding}"
    return x, y


def ffmpeg_drawtext_fontfile(font_name: str, bold: bool = False, italic: bool = False) -> str:
    path = watermark_font_path(font_name, bold, italic)
    return str(path).replace("\\", "/").replace(":", "\\:") if path else ""


def watermark_font_path(font_name: str, bold: bool = False, italic: bool = False) -> Path | None:
    font_dirs = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows" / "Fonts",
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts",
    ]
    requested = font_name.strip().lower().replace(" ", "")
    weight_names = ["bold", "semibold", "extrabold", "black"] if bold else ["regular", "medium", "light"]
    style_names = ["italic"] if italic else [""]
    matches: list[Path] = []
    for font_dir in font_dirs:
        if not font_dir.is_dir():
            continue
        for path in font_dir.glob("*.*tf"):
            normalized = path.stem.lower().replace(" ", "").replace("_", "").replace("-", "")
            if requested and requested not in normalized:
                continue
            score = 0
            has_italic = "italic" in normalized
            if italic == has_italic:
                score += 20
            if bold:
                if "bold" in normalized and "black" not in normalized and "extra" not in normalized:
                    score += 18
                elif "semibold" in normalized:
                    score += 12
                elif "extrabold" in normalized:
                    score += 9
                elif "black" in normalized:
                    score += 6
            else:
                if (italic and normalized == requested + "italic") or (
                    not italic and normalized == requested + "regular"
                ):
                    score += 22
                if "regular" in normalized:
                    score += 18
                elif "medium" in normalized:
                    score += 12
                elif "light" in normalized or "thin" in normalized:
                    score += 5
                if any(weight in normalized for weight in ("bold", "black", "extrabold")):
                    score -= 10
            if normalized == requested or normalized.startswith(requested + "regular"):
                score += 4
            matches.append((score, path))
    if matches:
        return sorted(matches, key=lambda item: item[0], reverse=True)[0][1]
    fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    if "tahoma" in requested:
        candidates = ["tahomabd.ttf" if bold else "tahoma.ttf"]
    elif "verdana" in requested:
        candidates = [
            "verdanaz.ttf" if bold and italic else
            "verdanab.ttf" if bold else
            "verdanai.ttf" if italic else
            "verdana.ttf"
        ]
    elif "segoe" in requested:
        candidates = [
            "segoeuiz.ttf" if bold and italic else
            "segoeuib.ttf" if bold else
            "segoeuii.ttf" if italic else
            "segoeui.ttf"
        ]
    else:
        candidates = [
            "arialbi.ttf" if bold and italic else
            "arialbd.ttf" if bold else
            "ariali.ttf" if italic else
            "arial.ttf"
        ]
    candidates.extend(["arialbd.ttf" if bold else "arial.ttf", "segoeui.ttf"])
    for name in candidates:
        path = fonts / name
        if path.is_file():
            return path
    return None


def rgba_from_hex(color: str, alpha: float = 1.0) -> tuple[int, int, int, int]:
    value = color.strip().lstrip("#")
    if len(value) != 6:
        value = "000000"
    try:
        r, g, b = int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
    except ValueError:
        r, g, b = 0, 0, 0
    return r, g, b, max(0, min(255, round(alpha * 255)))


def truthy(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "checked"}
    return bool(value)


def create_channel_name_overlay_image(name: str, config: dict, directory: Path, stem: str) -> Path:
    from PIL import Image, ImageDraw, ImageFont

    directory.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r'[<>:"/\\|?*]+', "_", stem).strip(" .") or "channel"
    path = directory / f"{safe}.png"
    style = config["style"]
    bold = truthy(style.get("bold", False))
    italic = truthy(style.get("italic", False))
    font_path = watermark_font_path(style["font"], bold, italic)
    try:
        font = ImageFont.truetype(str(font_path), int(style["font_size"])) if font_path else ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()
    padding_x = 20
    padding_y = 10
    temp = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    draw = ImageDraw.Draw(temp)
    bbox = draw.textbbox((0, 0), name, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    synthetic_italic = italic and (not font_path or "italic" not in font_path.stem.lower())
    italic_extra = round(text_h * 0.22) if synthetic_italic else 0
    width = text_w + padding_x * 2 + italic_extra
    height = text_h + padding_y * 2
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    mode = style.get("background", "None")
    opacity = float(style.get("background_opacity", 0.55))
    if mode != "None":
        bg = rgba_from_hex(style.get("background_color", "#000000"), opacity)
        radius = 0
        if mode in {"Round", "Rounded"}:
            radius = max(6, round(height * 0.22))
        elif mode == "Much rounded":
            radius = round(height * 0.48)
        rect = (0, 0, width - 1, height - 1)
        if radius:
            draw.rounded_rectangle(rect, radius=radius, fill=bg)
        else:
            draw.rectangle(rect, fill=bg)
    x = padding_x
    y = padding_y - bbox[1]
    text_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    text_draw = ImageDraw.Draw(text_layer)
    text_draw.text((x, y), name, font=font, fill=rgba_from_hex(style.get("text_color", "#FFFFFF"), opacity))
    if synthetic_italic:
        shear = -0.18
        text_layer = text_layer.transform(
            (width, height),
            Image.Transform.AFFINE,
            (1, shear, round(height * 0.18), 0, 1, 0),
            resample=Image.Resampling.BICUBIC,
        )
    image.alpha_composite(text_layer)
    image.save(path)
    return path


def media_duration_seconds(path: str) -> float:
    probe = ffprobe_executable()
    duration = 0.0
    stderr = ""
    if probe:
        result = subprocess.run(
            [
                probe, "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", path,
            ],
            capture_output=True, text=True,
            creationflags=0x08000000 if sys.platform == "win32" else 0,
        )
        stderr = result.stderr
        try:
            duration = float(result.stdout.strip())
        except ValueError:
            duration = 0.0
    if duration <= 0:
        result = subprocess.run(
            [ffmpeg_executable(), "-hide_banner", "-i", path],
            capture_output=True, text=True,
            creationflags=0x08000000 if sys.platform == "win32" else 0,
        )
        stderr = result.stderr
        match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", result.stderr)
        if match:
            hours, minutes, seconds = match.groups()
            duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    if duration <= 0:
        raise RuntimeError(f"Cannot read video duration:\n{stderr[-2000:]}")
    return duration


def align_caption_segments_to_media_duration(
    segments: list[dict], media_duration: float
) -> tuple[list[dict], float]:
    """Correct linear ASR clock drift when decoded audio outlasts the media timeline."""
    if not segments or media_duration <= 0:
        return segments, 1.0
    transcript_end = max(
        [
            float(segment.get("end", 0.0))
            for segment in segments
        ]
        + [
            float(word.get("end", 0.0))
            for segment in segments
            for word in segment.get("words", [])
        ]
    )
    # A transcript cannot legitimately extend beyond the media. This commonly happens
    # after stream-copy concatenation of many AAC segments because decoder sample time
    # and container PTS accumulate at slightly different rates.
    if transcript_end <= media_duration + 0.10:
        return segments, 1.0
    scale = media_duration / transcript_end
    if not 0.90 <= scale < 1.0:
        return segments, 1.0
    aligned = []
    for segment in segments:
        item = dict(segment)
        item["start"] = max(0.0, float(segment.get("start", 0.0)) * scale)
        item["end"] = min(media_duration, float(segment.get("end", 0.0)) * scale)
        item["words"] = [
            {
                **word,
                "start": max(0.0, float(word.get("start", 0.0)) * scale),
                "end": min(media_duration, float(word.get("end", 0.0)) * scale),
            }
            for word in segment.get("words", [])
        ]
        aligned.append(item)
    return aligned, scale


def media_has_audio(path: str) -> bool:
    probe = ffprobe_executable()
    if probe:
        try:
            result = subprocess.run(
                [
                    probe, "-v", "error", "-select_streams", "a",
                    "-show_entries", "stream=index", "-of", "csv=p=0", path,
                ],
                capture_output=True, text=True,
                creationflags=0x08000000 if sys.platform == "win32" else 0,
            )
            return bool(result.stdout.strip())
        except Exception:
            pass
    result = subprocess.run(
        [ffmpeg_executable(), "-hide_banner", "-i", path],
        capture_output=True, text=True,
        creationflags=0x08000000 if sys.platform == "win32" else 0,
    )
    return bool(re.search(r"Stream #\d+:\d+.*Audio:", result.stderr))


def media_video_size(path: str) -> tuple[int, int]:
    probe = ffprobe_executable()
    if probe:
        result = subprocess.run(
            [
                probe, "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", path,
            ],
            capture_output=True, text=True,
            creationflags=0x08000000 if sys.platform == "win32" else 0,
        )
        match = re.search(r"(\d+)x(\d+)", result.stdout)
        if match:
            return int(match.group(1)), int(match.group(2))
    result = subprocess.run(
        [ffmpeg_executable(), "-hide_banner", "-i", path],
        capture_output=True, text=True,
        creationflags=0x08000000 if sys.platform == "win32" else 0,
    )
    match = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", result.stderr)
    if match:
        return int(match.group(1)), int(match.group(2))
    raise RuntimeError(f"Cannot read video size:\n{result.stderr[-2000:]}")


def gemini_logo_box(
    width: int, height: int, logo_percent: int = 9, margin_percent: int = 7
) -> tuple[int, int, int, int]:
    """Return the padded Gemini sparkle region used by current landscape videos."""
    size = max(24, round(min(width, height) * logo_percent / 100))
    padding = max(4, round(size * 0.16))
    box_w = min(width - 2, (size + padding * 2) // 2 * 2)
    box_h = min(height - 2, (size + padding * 2) // 2 * 2)
    # Gemini/Veo places the visible sparkle noticeably in from the right and,
    # especially, above the bottom edge.  Use each frame axis independently;
    # the previous min-axis margin put the box in the extreme corner and missed it.
    margin_x = max(2, round(width * margin_percent / 100))
    margin_y = max(2, round(height * (margin_percent + 3) / 100))
    x = max(0, width - margin_x - box_w)
    y = max(0, height - margin_y - box_h)
    return x // 2 * 2, y // 2 * 2, box_w, box_h


def subscribe_overlay_starts(
    video_duration: float, first_start: float, overlay_duration: float
) -> list[float]:
    """Return the three timeline positions used by Watermark and Automation."""
    duration = max(0.0, float(video_duration))
    latest_start = max(0.0, duration - max(0.0, float(overlay_duration)))
    requested = [
        max(0.0, float(first_start)),
        duration / 2.0,
        max(0.0, duration - 20.0),
    ]
    return [min(start, latest_start) for start in requested]


def build_gemini_logo_command(
    source: str, output: str, x: int, y: int, width: int, height: int, codec: str,
    mask_path: Path | None = None,
) -> list[str]:
    video_filter = (
        f"removelogo=f={ffmpeg_filter_path(mask_path)}"
        if mask_path else f"delogo=x={x}:y={y}:w={width}:h={height}:show=0"
    )
    command = [
        ffmpeg_executable(), "-y", "-hide_banner", "-i", source,
        "-vf", video_filter,
        "-map", "0:v:0", "-map", "0:a?", "-c:v", codec,
    ]
    if codec in {"h264_nvenc", "hevc_nvenc"}:
        command.extend(["-preset", "p4", "-cq", "19"])
    elif codec == "h264_qsv":
        command.extend(["-global_quality", "19"])
    elif codec == "h264_amf":
        command.extend(["-quality", "speed", "-qp_i", "19", "-qp_p", "19"])
    command.extend([
        "-c:a", "copy", "-movflags", "+faststart",
        "-progress", "pipe:1", "-nostats", output,
    ])
    return command


def create_gemini_shape_mask(
    frame_width: int, frame_height: int, box: tuple[int, int, int, int], output: Path
) -> Path:
    """Create a tight two-sparkle mask so straight background details stay untouched."""
    from PIL import Image, ImageFilter

    x, y, width, height = box
    output.parent.mkdir(parents=True, exist_ok=True)
    mask = Image.new("L", (frame_width, frame_height), 0)
    alpha_asset = APP_RUNTIME_ROOT / "assets" / (
        "gemini_bg_96.png" if max(width, height) > 70 else "gemini_bg_48.png"
    )
    calibrated = Image.open(alpha_asset).convert("L").resize(
        (width, height), Image.Resampling.LANCZOS
    )
    # Convert every calibrated alpha pixel into a removal mask and dilate enough
    # to include H.264 ringing around the watermark, while leaving the empty
    # corners of the selection untouched.
    # The calibrated PNG contains a faint 1-3 luma compression floor outside
    # the sparkle.  Treating every value >= 2 as logo turned the whole selected
    # rectangle white, so FFmpeg/LaMa/temporal inpaint removed a box instead of
    # the actual Gemini shape.  Eight keeps the soft logo edge while rejecting
    # that background floor.
    calibrated = calibrated.point(lambda value: 255 if value >= 8 else 0)
    calibrated = calibrated.filter(ImageFilter.MaxFilter(9))
    mask.paste(calibrated, (x, y))
    mask.save(output)
    return output


def reverse_alpha_gemini_roi(roi, alpha, estimate_mask):
    """Adapt the calibrated alpha map to one compressed video frame."""
    import cv2
    import numpy as np

    roi_float = roi.astype(np.float32)
    background = cv2.inpaint(roi, estimate_mask, 3, cv2.INPAINT_TELEA).astype(np.float32)
    observed_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY).astype(np.float32)
    background_gray = cv2.cvtColor(
        background.astype(np.uint8), cv2.COLOR_BGR2GRAY
    ).astype(np.float32)
    valid = (alpha > 0.025) & (background_gray < 245.0)
    predictor = alpha * (255.0 - background_gray)
    response = observed_gray - background_gray
    denominator = float(np.sum((predictor[valid]) ** 2))
    strength = (
        float(np.sum(predictor[valid] * response[valid]) / denominator)
        if denominator > 1e-3 else 0.55
    )
    strength = min(1.25, max(0.12, strength))
    frame_alpha = np.minimum(alpha[:, :, None] * strength, 0.92)
    restored = (roi_float - frame_alpha * 255.0) / np.maximum(
        1.0 - frame_alpha, 0.08
    )
    return np.clip(restored, 0, 255).astype(np.uint8), strength


def detect_gemini_logo_in_region(
    frame_path: Path, region: tuple[int, int, int, int]
) -> tuple[tuple[int, int, int, int] | None, float]:
    """Find the two-sparkle Gemini mark inside a user-selected search region."""
    import cv2
    import numpy as np

    frame = cv2.imread(str(frame_path), cv2.IMREAD_GRAYSCALE)
    if frame is None:
        return None, 0.0
    frame_h, frame_w = frame.shape
    rx, ry, rw, rh = region
    rx = max(0, min(frame_w - 1, rx))
    ry = max(0, min(frame_h - 1, ry))
    rw = max(8, min(frame_w - rx, rw))
    rh = max(8, min(frame_h - ry, rh))
    roi = frame[ry:ry + rh, rx:rx + rw]
    # A white semi-transparent watermark is a stable positive local contrast.
    smooth = cv2.GaussianBlur(roi, (0, 0), 7.0)
    contrast = cv2.subtract(roi, smooth)
    contrast = cv2.GaussianBlur(contrast, (3, 3), 0)
    best_score = -1.0
    best_box = None
    max_size = min(rw, rh, max(40, round(min(frame_w, frame_h) * 0.14)))
    min_size = max(28, round(min(frame_w, frame_h) * 0.035))

    for size in range(min_size // 2 * 2, max_size + 1, 4):
        template_path = config_dir() / "tools_preview" / "_detect_template.png"
        # Generate the same two-sparkle silhouette used by the restoration mask.
        create_gemini_shape_mask(size, size, (0, 0, size, size), template_path)
        template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
        if template is None or template.shape[0] > rh or template.shape[1] > rw:
            continue
        template = cv2.GaussianBlur(template, (3, 3), 0)
        result = cv2.matchTemplate(contrast, template, cv2.TM_CCOEFF_NORMED)
        _min_value, max_value, _min_location, max_location = cv2.minMaxLoc(result)
        if max_value > best_score:
            best_score = float(max_value)
            best_box = (
                (rx + max_location[0]) // 2 * 2,
                (ry + max_location[1]) // 2 * 2,
                size,
                size,
            )
    # Below this threshold ordinary highlights and straight edges are too easy
    # to confuse with the small translucent sparkle.
    if best_score < 0.20:
        return None, best_score
    return best_box, best_score


def detect_gemini_logo_in_video(
    source: str, region: tuple[int, int, int, int] | None = None,
    sample_count: int = 12,
) -> tuple[tuple[int, int, int, int] | None, float, float]:
    """Detect the stationary Gemini sparkle by median voting across video frames."""
    import cv2
    import numpy as np
    from PIL import Image

    capture = cv2.VideoCapture(source)
    if not capture.isOpened():
        return None, 0.0, 0.0
    frame_count = max(1, int(capture.get(cv2.CAP_PROP_FRAME_COUNT)))
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 30.0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    indices = np.linspace(
        0, frame_count - 1, num=min(max(3, sample_count), frame_count), dtype=int
    )
    gray_frames: list[tuple[int, object]] = []
    for index in indices:
        capture.set(cv2.CAP_PROP_POS_FRAMES, int(index))
        ok, frame = capture.read()
        if ok:
            gray_frames.append((int(index), cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)))
    capture.release()
    if not gray_frames:
        return None, 0.0, 0.0

    if region is None:
        region = (
            round(width * 0.56), round(height * 0.48),
            round(width * 0.43), round(height * 0.51),
        )
    rx, ry, rw, rh = region
    rx = max(0, min(width - 1, rx))
    ry = max(0, min(height - 1, ry))
    rw = max(16, min(width - rx, rw))
    rh = max(16, min(height - ry, rh))

    asset = np.asarray(
        Image.open(APP_RUNTIME_ROOT / "assets" / "gemini_bg_96.png").convert("L")
    )
    min_size = max(28, round(min(width, height) * 0.035))
    max_size = min(rw, rh, max(64, round(min(width, height) * 0.11)))
    best_score = -1.0
    best_box: tuple[int, int, int, int] | None = None
    best_frame_scores: list[float] = []

    contrasts = []
    for _index, gray in gray_frames:
        roi = gray[ry:ry + rh, rx:rx + rw]
        smooth = cv2.GaussianBlur(roi, (0, 0), 7.0)
        contrasts.append(cv2.GaussianBlur(cv2.subtract(roi, smooth), (3, 3), 0))

    for size in range(min_size // 2 * 2, max_size + 1, 4):
        template = cv2.resize(asset, (size, size), interpolation=cv2.INTER_LANCZOS4)
        template = ((template >= 8).astype(np.uint8) * 255)
        template = cv2.GaussianBlur(template, (3, 3), 0)
        if template.shape[0] > rh or template.shape[1] > rw:
            continue
        responses = [
            cv2.matchTemplate(contrast, template, cv2.TM_CCOEFF_NORMED)
            for contrast in contrasts
        ]
        aggregate = np.median(np.stack(responses, axis=0), axis=0)
        _minimum, maximum, _minimum_location, location = cv2.minMaxLoc(aggregate)
        if maximum > best_score:
            best_score = float(maximum)
            best_box = (
                (rx + location[0]) // 2 * 2,
                (ry + location[1]) // 2 * 2,
                size,
                size,
            )
            best_frame_scores = [float(response[location[1], location[0]]) for response in responses]

    if best_box is None or best_score < 0.28:
        return None, max(0.0, best_score), 0.0
    worst_sample = max(range(len(best_frame_scores)), key=best_frame_scores.__getitem__)
    worst_time = gray_frames[worst_sample][0] / max(0.01, fps)
    return best_box, best_score, worst_time


def gemini_residual_is_safe(bright: float, dark: float, clipped: float) -> bool:
    """Reject even faint signed Gemini edges before recommending analytical output."""
    return bright < 0.10 and dark < 0.10 and clipped < 0.04


def gemini_original_source(path: Path) -> Path:
    """Resolve an app-generated result back to its original sibling video."""
    current = path
    pattern = re.compile(
        r"^(?P<base>.+)_no_gemini_logo_(?:mask|premium|temporal|lama)(?:_\d+)?$",
        re.IGNORECASE,
    )
    while True:
        match = pattern.match(current.stem)
        if not match:
            return current
        candidate = current.with_name(match.group("base") + current.suffix)
        if not candidate.is_file():
            return current
        current = candidate


def detect_video_scene_ranges(
    source: str, frame_count: int, min_scene_frames: int = 12,
) -> list[tuple[int, int]]:
    """Find hard cuts so temporal inpainting never borrows from another shot."""
    import cv2
    import numpy as np

    if frame_count <= min_scene_frames * 2:
        return [(0, frame_count)]
    capture = cv2.VideoCapture(source)
    if not capture.isOpened():
        return [(0, frame_count)]
    cuts = [0]
    previous_frame = None
    previous_hist = None
    index = 0
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        small = cv2.resize(frame, (160, 90), interpolation=cv2.INTER_AREA)
        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [24, 16], [0, 180, 0, 256])
        cv2.normalize(hist, hist)
        if previous_frame is not None and index - cuts[-1] >= min_scene_frames:
            pixel_change = float(
                np.mean(cv2.absdiff(small, previous_frame), dtype=np.float64) / 255.0
            )
            histogram_change = float(
                cv2.compareHist(previous_hist, hist, cv2.HISTCMP_BHATTACHARYYA)
            )
            # Similar-looking consecutive shots may have only a modest mean
            # pixel delta.  The histogram gate makes the lower threshold
            # selective while preventing temporal inpainting from borrowing
            # content across a real hard cut.
            if (
                (pixel_change >= 0.10 and histogram_change >= 0.30)
                or pixel_change >= 0.38
            ):
                cuts.append(index)
        previous_frame = small
        previous_hist = hist
        index += 1
    capture.release()
    actual_count = min(frame_count, max(1, index))
    if len(cuts) > 1 and actual_count - cuts[-1] < min_scene_frames:
        cuts.pop()
    boundaries = [*cuts, actual_count]
    return [
        (boundaries[i], boundaries[i + 1])
        for i in range(len(boundaries) - 1)
        if boundaries[i + 1] > boundaries[i]
    ] or [(0, actual_count)]


def score_gemini_video_residual(
    source: str, candidate: str, box: tuple[int, int, int, int],
    sample_count: int = 12,
) -> dict[str, float | bool]:
    """Score both a remaining bright logo and a dark reverse-alpha artifact."""
    import cv2
    import numpy as np

    source_cap = cv2.VideoCapture(source)
    result_cap = cv2.VideoCapture(candidate)
    if not source_cap.isOpened() or not result_cap.isOpened():
        source_cap.release()
        result_cap.release()
        return {
            "bright": 1.0, "dark": 1.0, "clipped": 1.0,
            "worst": 1.0, "worst_time": 0.0, "safe": False,
        }
    total = min(
        max(1, int(source_cap.get(cv2.CAP_PROP_FRAME_COUNT))),
        max(1, int(result_cap.get(cv2.CAP_PROP_FRAME_COUNT))),
    )
    fps = float(result_cap.get(cv2.CAP_PROP_FPS) or source_cap.get(cv2.CAP_PROP_FPS) or 30.0)
    x, y, width, height = box
    template = cv2.imread(
        str(APP_RUNTIME_ROOT / "assets" / (
            "gemini_bg_96.png" if max(width, height) > 70 else "gemini_bg_48.png"
        )),
        cv2.IMREAD_GRAYSCALE,
    )
    if template is None:
        source_cap.release()
        result_cap.release()
        return {
            "bright": 1.0, "dark": 1.0, "clipped": 1.0,
            "worst": 1.0, "worst_time": 0.0, "safe": False,
        }
    template = cv2.resize(template, (width, height), interpolation=cv2.INTER_LINEAR)
    support = template >= 8
    template_float = np.where(support, template.astype(np.float32), 0.0)
    template_float -= template_float.mean()
    template_norm = float(np.linalg.norm(template_float)) + 1e-6

    def signed_correlation(frame) -> float:
        roi = frame[y:y + height, x:x + width]
        if roi.shape[:2] != (height, width):
            return 0.0
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY).astype(np.float32)
        local = gray - cv2.GaussianBlur(gray, (0, 0), 5.0)
        local -= local.mean()
        return float(np.dot(local.ravel(), template_float.ravel()) /
                     ((np.linalg.norm(local) + 1e-6) * template_norm))

    worst = 0.0
    worst_time = 0.0
    bright_max = 0.0
    dark_max = 0.0
    clipped_max = 0.0
    for index in np.linspace(0, total - 1, num=min(sample_count, total), dtype=int):
        source_cap.set(cv2.CAP_PROP_POS_FRAMES, int(index))
        result_cap.set(cv2.CAP_PROP_POS_FRAMES, int(index))
        ok_source, source_frame = source_cap.read()
        ok_result, result_frame = result_cap.read()
        if not ok_source or not ok_result:
            continue
        before = max(0.04, signed_correlation(source_frame))
        after = signed_correlation(result_frame)
        bright = max(0.0, after) / max(0.20, before)
        dark = max(0.0, -after) / max(0.20, before)
        source_gray = cv2.cvtColor(
            source_frame[y:y + height, x:x + width], cv2.COLOR_BGR2GRAY
        )
        result_gray = cv2.cvtColor(
            result_frame[y:y + height, x:x + width], cv2.COLOR_BGR2GRAY
        )
        clipped = float(np.mean((result_gray[support] <= 4) & (source_gray[support] >= 18))) \
            if np.any(support) else 0.0
        frame_worst = max(bright, dark, clipped * 3.0)
        bright_max = max(bright_max, bright)
        dark_max = max(dark_max, dark)
        clipped_max = max(clipped_max, clipped)
        if frame_worst > worst:
            worst = frame_worst
            worst_time = int(index) / max(0.01, fps)
    source_cap.release()
    result_cap.release()
    # A 10-15% signed correlation is already visible as a thin diamond outline
    # on flat or dark backgrounds. Keep this deliberately strict so the UI
    # recommends the temporal result whenever analytical removal leaves a trace.
    safe = gemini_residual_is_safe(bright_max, dark_max, clipped_max)
    return {
        "bright": min(1.0, bright_max),
        "dark": min(1.0, dark_max),
        "clipped": min(1.0, clipped_max),
        "worst": min(1.0, worst),
        "worst_time": worst_time,
        "safe": safe,
    }


def gemini_temporal_roi(
    frame_width: int, frame_height: int, box: tuple[int, int, int, int],
    side: int = 384,
) -> tuple[int, int, int, int]:
    """Return a GPU-friendly square ROI with context around a tight logo box."""
    x, y, width, height = box
    side = max(max(width, height) + 32, min(side, frame_width, frame_height))
    side = max(64, side // 8 * 8)
    center_x = x + width // 2
    center_y = y + height // 2
    left = max(0, min(frame_width - side, center_x - side // 2))
    top = max(0, min(frame_height - side, center_y - side // 2))
    return left // 2 * 2, top // 2 * 2, side, side


def create_feathered_gemini_mask(source: Path, output: Path) -> Path:
    from PIL import Image, ImageFilter

    mask = Image.open(source).convert("L")
    mask = mask.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(2.4))
    mask.save(output)
    return output


def create_expanded_gemini_mask(source: Path, output: Path, padding: int) -> Path:
    """Cover the compressed halo around the logo before temporal inpainting."""
    from PIL import Image, ImageFilter

    padding = max(1, int(padding))
    mask = Image.open(source).convert("L")
    mask = mask.point(lambda value: 255 if value >= 8 else 0)
    mask = mask.filter(ImageFilter.MaxFilter(padding * 2 + 1))
    mask.save(output)
    return output


def build_watermark_ffmpeg_command(job: dict, config: dict) -> list[str]:
    command = [ffmpeg_executable(), "-y"]
    if config.get("codec") in {"auto", "h264_nvenc", "hevc_nvenc"}:
        command.extend(["-hwaccel", "cuda"])
    trailer = config.get("trailer", {})
    trailer_video = str(trailer.get("video", "")).strip()
    if trailer_video:
        command.extend(["-i", trailer_video])
    source_index = 1 if trailer_video else 0
    command.extend(["-i", job["input"]])
    warning = config["warning"]
    subscribe = config["subscribe"]
    logo = job.get("logo", "")
    if warning["image"]:
        command.extend(["-i", warning["image"]])
    if subscribe["video"]:
        command.extend(["-i", subscribe["video"]])
    if logo:
        command.extend(["-i", logo])
    channel_variants = list(job.get("channel_variants") or [])
    for variant in channel_variants:
        command.extend(["-i", str(variant["overlay"])])
    channel_overlay = str(job.get("channel_overlay", "")).strip()
    if (
        not channel_variants
        and config.get("render_channel_name", True)
        and not channel_overlay
        and job.get("name")
    ):
        overlay_dir = Path(job["output"]).parent / "_watermark_assets"
        channel_overlay = str(create_channel_name_overlay_image(
            str(job["name"]), config, overlay_dir, Path(job["output"]).stem + "_channel"
        ))
    if channel_overlay:
        command.extend(["-i", channel_overlay])
    filters = []
    current = f"{source_index}:v"
    next_input = source_index + 1
    audio_map: str | None = None
    source_duration = media_duration_seconds(job["input"])
    trailer_duration = 0.0
    source_width, source_height = media_video_size(job["input"])
    caption_path = str(job.get("caption", "")).strip()
    if trailer_video:
        trailer_duration = media_duration_seconds(trailer_video)
        transition_duration = max(0.05, float(trailer.get("transition", 0.5)))
        transition_duration = min(transition_duration, max(0.05, trailer_duration / 2))
        fade_out_start = max(0, trailer_duration - transition_duration)
        filters.append(
            f"[0:v]scale={source_width}:{source_height},setsar=1,format=yuv420p,"
            f"fade=t=out:st={fade_out_start}:d={transition_duration}[trailer_v]"
        )
        filters.append(
            f"[{source_index}:v]scale={source_width}:{source_height},setsar=1,format=yuv420p,"
            f"fade=t=in:st=0:d={transition_duration}[source_v]"
        )
        source_concat = "source_v"
        if caption_path:
            filters.append(f"[source_v]subtitles={ffmpeg_filter_path(Path(caption_path))}[source_cap]")
            source_concat = "source_cap"
        filters.append(f"[trailer_v][{source_concat}]concat=n=2:v=1:a=0[basev]")
        current = "basev"
        trailer_has_audio = media_has_audio(trailer_video)
        source_has_audio = media_has_audio(job["input"])
        if trailer_has_audio and source_has_audio:
            filters.append("[0:a]aresample=async=1:first_pts=0[trailer_a]")
            filters.append(f"[{source_index}:a]aresample=async=1:first_pts=0[source_a]")
            filters.append("[trailer_a][source_a]concat=n=2:v=0:a=1[outa]")
            audio_map = "[outa]"
        elif trailer_has_audio:
            filters.append("[0:a]aresample=async=1:first_pts=0[outa]")
            audio_map = "[outa]"
        elif source_has_audio:
            delay_ms = max(0, round(trailer_duration * 1000))
            filters.append(f"[{source_index}:a]adelay={delay_ms}:all=1[outa]")
            audio_map = "[outa]"
    if caption_path and not trailer_video:
        filters.append(f"[{current}]subtitles={ffmpeg_filter_path(Path(caption_path))}[vcap]")
        current = "vcap"
    if warning["image"]:
        if warning["fit"] == "Crop":
            filters.append(
                f"[{next_input}:v]scale={source_width}:{source_height}:"
                f"force_original_aspect_ratio=increase,"
                f"crop={source_width}:{source_height},setsar=1[warn]"
            )
        else:
            filters.append(f"[{next_input}:v]scale={source_width}:{source_height},setsar=1[warn]")
        filters.append(f"[{current}][warn]overlay=0:0:enable='lt(t,{warning['duration']})'[v1]")
        current, next_input = "v1", next_input + 1
    if subscribe["video"]:
        subscribe_duration = float(subscribe.get("duration") or media_duration_seconds(subscribe["video"]))
        timeline_duration = source_duration + trailer_duration
        subscribe_starts = subscribe_overlay_starts(
            timeline_duration, float(subscribe["start"]), subscribe_duration
        )
        scale = subscribe["scale"] / 100
        sx, sy = watermark_xy(subscribe["position"], config["padding_x"], config["padding_y"], True)
        count = len(subscribe_starts)
        if count > 1:
            split_outputs = "".join(f"[subsrc{n}]" for n in range(count))
            filters.append(f"[{next_input}:v]split={count}{split_outputs}")
        for n, start in enumerate(subscribe_starts):
            source_label = f"subsrc{n}" if count > 1 else f"{next_input}:v"
            sub_chain = (
                f"[{source_label}]trim=duration={subscribe_duration},"
                f"setpts=PTS-STARTPTS+{start}/TB,"
                f"scale=iw*{scale}:ih*{scale}"
            )
            if subscribe["chroma_key"]:
                color = subscribe["chroma_color"].lstrip("#")
                sub_chain += f",format=rgba,colorkey=0x{color}:{subscribe['similarity']}:{subscribe['blend']}"
            sub_label = f"sub{n}"
            out_label = f"vsub{n}"
            filters.append(sub_chain + f"[{sub_label}]")
            filters.append(
                f"[{current}][{sub_label}]overlay={sx}:{sy}:eof_action=pass:shortest=0:format=auto[{out_label}]"
            )
            current = out_label
        next_input += 1

        # Generate one gentle one-second bell and place a copy at each subscribe appearance.
        if audio_map:
            base_audio_source = audio_map
        elif media_has_audio(job["input"]):
            base_audio_source = f"[{source_index}:a]"
        else:
            filters.append(
                f"anullsrc=channel_layout=stereo:sample_rate=48000:d={timeline_duration}[silent_base]"
            )
            base_audio_source = "[silent_base]"
        filters.append(
            f"{base_audio_source}aresample=48000,apad,"
            f"atrim=duration={timeline_duration}[subscribe_base_audio]"
        )
        filters.append(
            "sine=frequency=1046:sample_rate=48000:duration=1,"
            "volume=0.10,afade=t=out:st=0.25:d=0.75[subscribe_bell]"
        )
        bell_raw_labels = "".join(f"[subscribe_bell_raw{n}]" for n in range(count))
        filters.append(f"[subscribe_bell]asplit={count}{bell_raw_labels}")
        bell_labels = []
        for n, start in enumerate(subscribe_starts):
            bell_label = f"subscribe_bell_{n}"
            filters.append(
                f"[subscribe_bell_raw{n}]adelay={round(start * 1000)}:all=1[{bell_label}]"
            )
            bell_labels.append(f"[{bell_label}]")
        filters.append(
            "[subscribe_base_audio]"
            + "".join(bell_labels)
            + f"amix=inputs={count + 1}:duration=first:dropout_transition=0:"
              "normalize=0[subscribe_audio]"
        )
        audio_map = "[subscribe_audio]"
    if logo:
        filters.append(f"[{next_input}:v]scale=160:-1[logo]")
        lx, ly = watermark_xy(config["position"], config["padding_x"], config["padding_y"], True)
        filters.append(f"[{current}][logo]overlay={lx}:{ly}:eof_action=repeat[vlogo]")
        current, next_input = "vlogo", next_input + 1
    variant_video_labels: list[str] = []
    if channel_variants:
        split_labels = "".join(
            f"[channel_base_{index}]" for index in range(len(channel_variants))
        )
        filters.append(f"[{current}]split={len(channel_variants)}{split_labels}")
        ox, oy = watermark_xy(config["position"], config["padding_x"], config["padding_y"], True)
        name_start = float(config.get("name_start", 0) or 0)
        enable = f":enable='gte(t,{name_start})'" if name_start > 0 else ""
        for index, _variant in enumerate(channel_variants):
            label = f"vchan_{index}"
            filters.append(
                f"[channel_base_{index}][{next_input + index}:v]"
                f"overlay={ox}:{oy}:eof_action=repeat:format=auto{enable}[{label}]"
            )
            variant_video_labels.append(label)
        next_input += len(channel_variants)
    elif channel_overlay:
        ox, oy = watermark_xy(config["position"], config["padding_x"], config["padding_y"], True)
        name_start = float(config.get("name_start", 0) or 0)
        enable = f":enable='gte(t,{name_start})'" if name_start > 0 else ""
        filters.append(
            f"[{current}][{next_input}:v]overlay={ox}:{oy}:eof_action=repeat:format=auto{enable}[vchan]"
        )
        current, next_input = "vchan", next_input + 1
    target_width = int(config.get("target_width") or source_width)
    target_height = int(config.get("target_height") or source_height)
    target_fps = int(config.get("target_fps") or 0)
    final_chain = (
        f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,"
        f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2,setsar=1"
    )
    if target_fps > 0:
        final_chain += f",fps={target_fps}"
    final_chain += ",format=yuv420p"
    codec = config["codec"]
    if codec == "auto":
        codec = require_video_gpu_codec()

    def append_output_codec_options() -> None:
        command.extend(["-c:v", codec])
        if codec == "libx264":
            command.extend(["-preset", "veryfast", "-crf", str(config["crf"])])
        elif codec in {"h264_nvenc", "hevc_nvenc"}:
            command.extend(["-preset", "p2", "-cq", str(max(22, int(config["crf"])))])
        elif codec == "h264_qsv":
            command.extend(["-preset", "faster", "-global_quality", str(config["crf"])])
        elif codec == "h264_amf":
            command.extend([
                "-quality", "speed", "-qp_i", str(config["crf"]),
                "-qp_p", str(config["crf"]),
            ])
        command.extend(["-c:a", "aac" if audio_map else "copy"])
        command.extend(["-movflags", "+faststart", "-shortest"])

    if channel_variants:
        final_labels = []
        for index, label in enumerate(variant_video_labels):
            final_label = f"outv_{index}"
            filters.append(f"[{label}]{final_chain}[{final_label}]")
            final_labels.append(final_label)
        audio_labels: list[str] = []
        if audio_map:
            audio_labels = [f"outa_{index}" for index in range(len(channel_variants))]
            filters.append(
                f"{audio_map}asplit={len(audio_labels)}"
                + "".join(f"[{label}]" for label in audio_labels)
            )
        command.extend(["-filter_complex", ";".join(filters), "-progress", "pipe:1", "-nostats"])
        for index, variant in enumerate(channel_variants):
            command.extend(["-map", f"[{final_labels[index]}]"])
            command.extend([
                "-map",
                f"[{audio_labels[index]}]" if audio_labels else f"{source_index}:a?",
            ])
            append_output_codec_options()
            command.append(str(variant["output"]))
    else:
        filters.append(f"[{current}]{final_chain}[outv]")
        command.extend(["-filter_complex", ";".join(filters), "-map", "[outv]"])
        if audio_map:
            command.extend(["-map", audio_map])
        else:
            command.extend(["-map", f"{source_index}:a?"])
        append_output_codec_options()
        command.extend(["-progress", "pipe:1", "-nostats", job["output"]])
    return command


class ChannelMultiSelectCombo(QComboBox):
    selection_changed = Signal(list)

    def __init__(self, channels: list[str], selected: list[str] | None = None) -> None:
        super().__init__()
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)
        self.lineEdit().setPlaceholderText("Chọn một hoặc nhiều kênh")
        self.setModel(QStandardItemModel(self))
        self._keep_popup_open = False
        self.view().pressed.connect(self._toggle_item)
        self.activated.connect(lambda _index: self._update_display())
        self.set_channels(channels, selected)

    def set_channels(self, channels: list[str], selected: list[str] | None = None) -> None:
        selected_set = set(selected if selected is not None else channels)
        model = self.model()
        model.clear()
        for channel in channels:
            item = QStandardItem(channel)
            item.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsUserCheckable
            )
            item.setData(
                Qt.CheckState.Checked if channel in selected_set else Qt.CheckState.Unchecked,
                Qt.ItemDataRole.CheckStateRole,
            )
            model.appendRow(item)
        self._update_display()

    def selected_channels(self) -> list[str]:
        model = self.model()
        return [
            model.item(row).text()
            for row in range(model.rowCount())
            if model.item(row).checkState() == Qt.CheckState.Checked
        ]

    def _toggle_item(self, index) -> None:
        self._keep_popup_open = True
        item = self.model().itemFromIndex(index)
        item.setCheckState(
            Qt.CheckState.Unchecked
            if item.checkState() == Qt.CheckState.Checked
            else Qt.CheckState.Checked
        )
        self._update_display()
        self.selection_changed.emit(self.selected_channels())

    def _update_display(self) -> None:
        selected = self.selected_channels()
        self.lineEdit().setText(", ".join(selected))
        self.lineEdit().setToolTip("\n".join(selected))

    def hidePopup(self) -> None:
        if self._keep_popup_open:
            self._keep_popup_open = False
            return
        super().hidePopup()


AUTOMATION_GROUP_CAPTION_WATERMARK = "Caption + Watermark"
AUTOMATION_GROUP_VIDEO_EFFECT_CAPTION_WATERMARK = "Video Effect + Caption + Watermark"
AUTOMATION_GROUP_FULL_PIPELINE = "Voice Clone + Video Effect + Caption + Watermark"
AUTOMATION_GROUP_WATERMARK_ONLY = "Watermark only"
AUTOMATION_PROCESSING_GROUPS = (
    AUTOMATION_GROUP_CAPTION_WATERMARK,
    AUTOMATION_GROUP_VIDEO_EFFECT_CAPTION_WATERMARK,
    AUTOMATION_GROUP_FULL_PIPELINE,
    AUTOMATION_GROUP_WATERMARK_ONLY,
)
AUTOMATION_BATCH_GROUPS = ("Group 1", "Group 2", "Group 3")
AUTOMATION_BATCH_GROUP_ALIASES = {
    "Nhóm 1": "Group 1",
    "Nhóm 2": "Group 2",
    "Nhóm 3": "Group 3",
}


class AutomationTableWidget(QTableWidget):
    files_dropped = Signal(list, int, int)
    rows_reordered = Signal()

    def __init__(self, rows: int, columns: int) -> None:
        super().__init__(rows, columns)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls() or event.source() is self:
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls() or event.source() is self:
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            paths = [
                url.toLocalFile()
                for url in event.mimeData().urls()
                if url.isLocalFile() and url.toLocalFile()
            ]
            if paths:
                index = self.indexAt(event.position().toPoint())
                row = index.row() if index.isValid() else self.rowCount()
                column = index.column() if index.isValid() else -1
                self.files_dropped.emit(paths, row, column)
                event.acceptProposedAction()
                return
        if event.source() is self:
            self.move_selected_rows_to_drop_position(event)
            event.acceptProposedAction()
            return
        super().dropEvent(event)

    def move_selected_rows_to_drop_position(self, event) -> None:
        selected_rows = sorted({index.row() for index in self.selectedIndexes()})
        if not selected_rows:
            return
        target = self.indexAt(event.position().toPoint()).row()
        if target < 0:
            target = self.rowCount()
        row_values = [
            [
                self.item(row, column).text() if self.item(row, column) else ""
                for column in range(self.columnCount())
            ]
            for row in selected_rows
        ]
        for row in reversed(selected_rows):
            self.removeRow(row)
        removed_before_target = sum(1 for row in selected_rows if row < target)
        target = max(0, min(self.rowCount(), target - removed_before_target))
        for offset, values in enumerate(row_values):
            self.insertRow(target + offset)
            for column, value in enumerate(values):
                self.setItem(target + offset, column, QTableWidgetItem(value))
        self.clearSelection()
        for row in range(target, target + len(row_values)):
            self.selectRow(row)
        self.rows_reordered.emit()


class MainWindow(QMainWindow):
    WINDOW_CORNER_RADIUS = 16

    def apply_initial_window_size(self) -> None:
        screen = QApplication.primaryScreen()
        if not screen:
            self.resize(1280, 760)
            return
        available = screen.availableGeometry()
        width = min(1280, max(900, available.width() - 32), available.width())
        height = min(850, max(560, available.height() - 48), available.height())
        x = available.x() + max(0, (available.width() - width) // 2)
        y = available.y() + 16
        self.setGeometry(x, y, width, height)

    def apply_native_rounded_corners(self) -> None:
        if sys.platform != "win32":
            return
        try:
            import ctypes

            DWMWA_WINDOW_CORNER_PREFERENCE = 33
            DWMWCP_ROUND = 2
            preference = ctypes.c_int(DWMWCP_ROUND)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                int(self.winId()),
                DWMWA_WINDOW_CORNER_PREFERENCE,
                ctypes.byref(preference),
                ctypes.sizeof(preference),
            )
        except Exception:
            pass

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.update()

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            self.update()

    def build_window_brand_widget(self) -> QWidget:
        brand = QWidget()
        brand.setObjectName("windowBrand")
        brand.setCursor(Qt.CursorShape.OpenHandCursor)
        brand.installEventFilter(self)
        layout = QHBoxLayout(brand)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(8)

        self.language_toggle_button = QPushButton("EN / VI")
        self.language_toggle_button.setObjectName("languageToggleButton")
        self.language_toggle_button.setFixedSize(62, 28)
        self.language_toggle_button.setToolTip("Language / Ngôn ngữ")
        self.language_toggle_button.clicked.connect(self.toggle_ui_language)

        minimize = QPushButton("-")
        maximize = QPushButton("□")
        close = QPushButton("×")
        for button in (minimize, maximize, close):
            button.setObjectName("windowControlButton")
            button.setFixedSize(30, 28)
            button.setCursor(Qt.CursorShape.ArrowCursor)
        close.setObjectName("windowCloseButton")
        minimize.setToolTip("Minimize")
        maximize.setToolTip("Maximize / Restore")
        close.setToolTip("Close")
        minimize.clicked.connect(self.showMinimized)
        maximize.clicked.connect(self.toggle_maximized)
        close.clicked.connect(self.close)

        logo = QLabel()
        logo.setObjectName("windowBrandLogo")
        if (APP_ROOT / "assets" / "voice.png").is_file():
            pixmap = QPixmap(str(APP_ROOT / "assets" / "voice.png"))
            logo.setPixmap(
                pixmap.scaled(
                    22, 22,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        logo.setFixedSize(24, 24)

        title = QLabel(f"{APP_NAME} {APP_VERSION}")
        title.setObjectName("windowBrandTitle")
        title.setCursor(Qt.CursorShape.OpenHandCursor)
        title.installEventFilter(self)
        self.window_brand_widget = brand
        self.window_brand_title = title

        layout.addWidget(self.language_toggle_button)
        layout.addWidget(minimize)
        layout.addWidget(maximize)
        layout.addWidget(close)
        layout.addSpacing(4)
        layout.addWidget(logo)
        layout.addWidget(title)
        return brand

    def translated_ui_text(self, text: str) -> str:
        """Return Vietnamese UI copy without changing technical values."""
        if not text or self.ui_language != "vi":
            return text
        if text in VI_UI:
            return VI_UI[text]
        translated = text
        for english, vietnamese in VI_PHRASES:
            translated = translated.replace(english, vietnamese)
        return translated

    def translated_log_text(self, text: str) -> str:
        """Translate human-readable log prose while preserving paths and technical terms."""
        if not text or self.ui_language != "vi":
            return text
        protected: list[str] = []

        def protect(match: re.Match) -> str:
            protected.append(match.group(0))
            return f"\x00{len(protected) - 1}\x00"

        # Do not alter URLs, filesystem paths, filenames, quoted values or identifiers.
        result = re.sub(
            r"https?://\S+|[A-Za-z]:[\\/]\S+|(?:^|(?<=\s))/\S+|"
            r"\b\S+\.(?:wav|mp3|mp4|mkv|srt|txt|json|png|jpg|jpeg|webp)\b|"
            r"'[^']*'|\"[^\"]*\"",
            protect,
            text,
            flags=re.MULTILINE | re.IGNORECASE,
        )
        result = VI_UI.get(result, result)
        for pattern, replacement in VI_LOG_PHRASES:
            result = re.sub(pattern, replacement, result)
        for index, value in enumerate(protected):
            result = result.replace(f"\x00{index}\x00", value)
        return result

    def _translate_widget_value(self, widget: QWidget, getter: str, setter: str, key: str) -> None:
        get_value = getattr(widget, getter, None)
        set_value = getattr(widget, setter, None)
        if not callable(get_value) or not callable(set_value):
            return
        original = widget.property(key)
        if original is None:
            original = get_value()
            widget.setProperty(key, original)
        set_value(self.translated_ui_text(str(original)))

    def apply_ui_language(self) -> None:
        """Retranslate every static widget while retaining the original English copy."""
        root = self.centralWidget()
        if root is None:
            return
        widgets = [root, *root.findChildren(QWidget)]
        for widget in widgets:
            retranslate_log = getattr(widget, "retranslate", None)
            if isinstance(widget, QPlainTextEdit) and callable(retranslate_log):
                retranslate_log()
            if isinstance(widget, (QLabel, QPushButton, QCheckBox, QRadioButton)):
                self._translate_widget_value(widget, "text", "setText", "_i18n_text")
            if isinstance(widget, QGroupBox):
                self._translate_widget_value(widget, "title", "setTitle", "_i18n_title")
            self._translate_widget_value(widget, "toolTip", "setToolTip", "_i18n_tooltip")
            self._translate_widget_value(
                widget, "placeholderText", "setPlaceholderText", "_i18n_placeholder"
            )
            if isinstance(widget, QTabWidget):
                for index in range(widget.count()):
                    page = widget.widget(index)
                    original = page.property("_i18n_tab_text")
                    if original is None:
                        original = widget.tabText(index)
                        page.setProperty("_i18n_tab_text", original)
                    widget.setTabText(index, self.translated_ui_text(str(original)))
            if isinstance(widget, QTableWidget):
                for column in range(widget.columnCount()):
                    item = widget.horizontalHeaderItem(column)
                    if item is None:
                        continue
                    original = item.data(Qt.ItemDataRole.UserRole + 91)
                    if original is None:
                        original = item.text()
                        item.setData(Qt.ItemDataRole.UserRole + 91, original)
                    item.setText(self.translated_ui_text(str(original)))
            if isinstance(widget, QComboBox) and not widget.isEditable():
                # Only translate entries backed by stable itemData. Business logic
                # continues to read the unchanged data value instead of display text.
                for index in range(widget.count()):
                    if widget.itemData(index) is None:
                        continue
                    original = widget.itemData(index, Qt.ItemDataRole.UserRole + 92)
                    if original is None:
                        original = widget.itemText(index)
                        widget.setItemData(index, original, Qt.ItemDataRole.UserRole + 92)
                    translated = self.translated_ui_text(str(original))
                    widget.setItemText(index, translated)
        self.language_toggle_button.setText("VI" if self.ui_language == "vi" else "EN")
        self.language_toggle_button.setToolTip(
            "Chuyển sang tiếng Anh" if self.ui_language == "vi" else "Switch to Vietnamese"
        )
        self.refresh_license_information()

    def refresh_license_information(self) -> None:
        if not hasattr(self, "license_status_value"):
            return
        request_id = hardware_request_id()
        expiry = saved_activation_expiry(config_dir(), request_id)
        self.license_request_value.setText(request_id)
        if expiry is None:
            self.license_status_value.setText("Đã hết hạn" if self.ui_language == "vi" else "Expired")
            self.license_expiry_value.setText("—")
            self.license_remaining_value.setText("0 ngày" if self.ui_language == "vi" else "0 days")
            return
        days = max(0, (expiry - datetime.now().date()).days)
        self.license_status_value.setText("Đã kích hoạt" if self.ui_language == "vi" else "Activated")
        self.license_expiry_value.setText(expiry.strftime("%d/%m/%Y"))
        if self.ui_language == "vi":
            self.license_remaining_value.setText(f"{days} ngày")
        else:
            suffix = "day" if days == 1 else "days"
            self.license_remaining_value.setText(f"{days} {suffix}")

    def copy_license_request_id(self) -> None:
        QApplication.clipboard().setText(self.license_request_value.text())
        self.license_copy_button.setText("Đã sao chép" if self.ui_language == "vi" else "Copied")
        QTimer.singleShot(1600, self.reset_license_copy_button)

    def reset_license_copy_button(self) -> None:
        self.license_copy_button.setText("Sao chép" if self.ui_language == "vi" else "Copy")

    def toggle_ui_language(self) -> None:
        self.ui_language = "en" if self.ui_language == "vi" else "vi"
        self.settings["ui_language"] = self.ui_language
        save_settings({**self.current_settings_payload(), "ui_language": self.ui_language})
        self.apply_ui_language()

    def toggle_maximized(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def handle_window_drag_event(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._drag_source = watched
            if hasattr(watched, "setCursor"):
                watched.setCursor(Qt.CursorShape.ClosedHandCursor)
            return True
        if (
            event.type() == QEvent.Type.MouseMove
            and event.buttons() & Qt.MouseButton.LeftButton
            and getattr(self, "_drag_source", None) is watched
        ):
            if not self.isMaximized() and hasattr(self, "_drag_position"):
                self.move(event.globalPosition().toPoint() - self._drag_position)
            return True
        if event.type() == QEvent.Type.MouseButtonRelease and getattr(self, "_drag_source", None) is watched:
            if hasattr(watched, "setCursor"):
                if watched in {
                    getattr(self, "window_brand_widget", None),
                    getattr(self, "window_brand_title", None),
                }:
                    watched.setCursor(Qt.CursorShape.OpenHandCursor)
                else:
                    watched.unsetCursor()
            self._drag_source = None
            return True
        if event.type() == QEvent.Type.MouseButtonDblClick and event.button() == Qt.MouseButton.LeftButton:
            self.toggle_maximized()
            return True
        return False

    def is_tab_bar_empty_drag_area(self, watched: QObject, event: QEvent) -> bool:
        if watched is getattr(self, "main_tab_bar", None):
            return watched.tabAt(event.position().toPoint()) < 0
        if watched is getattr(self, "main_tabs", None):
            tab_bar = getattr(self, "main_tab_bar", None)
            if not tab_bar or event.position().y() > tab_bar.height() + 8:
                return False
            tab_bar_pos = tab_bar.mapFrom(watched, event.position().toPoint())
            return tab_bar.tabAt(tab_bar_pos) < 0
        return False

    def update_top_drag_cursor(self, watched: QObject, event: QEvent) -> None:
        if (
            event.type() == QEvent.Type.MouseMove
            and not event.buttons()
            and self.is_tab_bar_empty_drag_area(watched, event)
        ):
            watched.setCursor(Qt.CursorShape.OpenHandCursor)
        elif getattr(self, "_drag_source", None) is not watched:
            watched.unsetCursor()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched in {getattr(self, "window_brand_widget", None), getattr(self, "window_brand_title", None)}:
            if self.handle_window_drag_event(watched, event):
                return True

        if watched is getattr(self, "main_tab_bar", None):
            if event.type() in {QEvent.Type.MouseMove, QEvent.Type.Leave}:
                self.update_top_drag_cursor(watched, event)
            if event.type() in {
                QEvent.Type.MouseButtonPress,
                QEvent.Type.MouseButtonDblClick,
            }:
                if not self.is_tab_bar_empty_drag_area(watched, event):
                    return False
                return self.handle_window_drag_event(watched, event)
            if self.handle_window_drag_event(watched, event):
                return True

        if watched is getattr(self, "main_tabs", None):
            tab_bar = getattr(self, "main_tab_bar", None)
            if event.type() in {QEvent.Type.MouseMove, QEvent.Type.Leave}:
                self.update_top_drag_cursor(watched, event)
            if tab_bar and event.type() in {
                QEvent.Type.MouseButtonPress,
                QEvent.Type.MouseButtonDblClick,
            }:
                if self.is_tab_bar_empty_drag_area(watched, event):
                    return self.handle_window_drag_event(watched, event)
            if self.handle_window_drag_event(watched, event):
                return True
        return super().eventFilter(watched, event)

    def __init__(self) -> None:
        super().__init__()
        cuda_label = os.environ.get("VOICEOVER_CUDA_LABEL", "CUDA auto")
        self.setObjectName("mainWindow")
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION} - OmniVoice {cuda_label}")
        if APP_ICON.is_file():
            self.setWindowIcon(QIcon(str(APP_ICON)))
        self.apply_initial_window_size()
        self.apply_native_rounded_corners()
        self.store = ProfileStore()
        self.settings = load_settings()
        bundled_subscribe = APP_ROOT / "assets" / "red-subscribe-like-noti.mp4"
        if not str(self.settings.get("watermark_subscribe_video", "")).strip() and bundled_subscribe.is_file():
            self.settings["watermark_subscribe_video"] = str(bundled_subscribe)
        bundled_oldman = config_dir() / "profiles" / "ingamar-oldman-v2b" / "profile.json"
        if not str(self.settings.get("default_voice_profile", "")).strip() and bundled_oldman.is_file():
            self.settings["default_voice_profile"] = "ingamar-oldman-v2b"
        self.ui_language = "vi" if self.settings.get("ui_language") == "vi" else "en"
        self.default_voice_profile_name = self.settings.get("default_voice_profile", "")
        self.thread: QThread | None = None
        self.worker: QObject | None = None
        self.preload_thread: QThread | None = None
        self.preload_worker: QObject | None = None
        self.voice_preview_player: QMediaPlayer | None = None
        self.voice_preview_audio_output: QAudioOutput | None = None
        self.active_task_ui = "omnivoice"
        self.render_started_at: float | None = None
        self.segment_style_overrides: dict[int, str] = {}
        self.active_output_dir: Path | None = None
        self.active_omnivoice_profile = ""
        self.active_omnivoice_suffix = ""
        self.active_zonos2_output_dir: Path | None = None
        self.active_video_effect_output_dir: Path | None = None
        self.video_effect_batch_rows: list[dict] = []
        self.video_effect_batch_queue: list[dict] = []
        self.video_effect_batch_outputs: list[str] = []
        self.video_effect_batch_index = 0
        self.video_effect_batch_started_at: float | None = None
        self.video_effect_batch_stopping = False
        self.video_effect_job_succeeded = False
        self.video_integrity_thread: QThread | None = None
        self.video_integrity_worker: VideoIntegrityCheckWorker | None = None
        self.video_output_merge_thread: QThread | None = None
        self.video_output_merge_worker: OutputVideoMergeWorker | None = None
        self.video_effect_preflight_thread: QThread | None = None
        self.video_effect_preflight_worker: VideoEffectMediaPreflightWorker | None = None
        self.video_effect_pending_jobs: list[dict] = []
        self.zonos2_session_id = uuid.uuid4().hex

        self.profile = QComboBox()
        self.voice_profile = QComboBox()
        self.clone_language = QComboBox()
        self.clone_language.addItem("English reference", "en")
        self.clone_language.addItem("Vietnamese reference", "vi")
        self.profile_name = QLineEdit()
        self.profile_name.setPlaceholderText(
            "Leave blank to overwrite the selected voice transcript"
        )
        self.reference_audio = QLineEdit()
        self.reference_text = QPlainTextEdit()
        self.reference_text.setPlaceholderText(
            "Optional. Leave blank to let Whisper auto-transcribe."
        )
        self.is_batch_running = False
        self.render_queue = []
        self.current_rendering_file_name = ""
        self.batch_rows = []
        self.segment_text_input = QPlainTextEdit()
        self.segment_text_input.setPlaceholderText(
            "Paste one or more segments here. Separate segments with a blank line."
        )
        self.segment_text_input.setMaximumHeight(110)
        self.language = QComboBox()
        self.language.addItem("Auto detect", None)
        self.language.addItem("English", "en")
        self.language.addItem("Vietnamese", "vi")
        self.language.setCurrentIndex(max(0, self.language.findData(self.settings["language"] or None)))
        self.model_name = QLineEdit(self.settings["model_name"])
        self.steps = QSpinBox()
        self.steps.setRange(8, 64)
        self.steps.setValue(setting_int(self.settings, "steps"))
        self.fit_timeline = QCheckBox("Fit generated audio to each SRT timestamp duration")
        self.fit_timeline.setChecked(setting_bool(self.settings, "fit_timeline"))
        self.normalize_audio = QCheckBox("Normalize completed batch after all segments render")
        self.normalize_audio.setChecked(setting_bool(self.settings, "normalize_audio"))
        self.normalize_audio.setToolTip(
            "Off preserves original OmniVoice output. On measures speech loudness after all "
            "segments exist, then applies one constant gain per file with a light limiter."
        )
        self.overwrite_existing = QCheckBox("Overwrite existing files in selected range")
        self.range_from = QSpinBox()
        self.range_from.setRange(1, 1)
        self.range_to = QSpinBox()
        self.range_to.setRange(1, 1)
        self.output_format = QComboBox()
        self.output_format.addItems(["wav", "mp3"])
        self.output_format.setCurrentText(self.settings["output_format"])
        self.compute_device = QComboBox()
        runtime_device = os.environ.get("VOICEOVER_DEFAULT_DEVICE", "cuda")
        cpu_label = "CPU mode" if runtime_device == "cpu" else "CPU diagnostic (safe, very slow)"
        self.compute_device.addItem(cpu_label, "cpu")
        if runtime_device != "cpu":
            cuda_label = os.environ.get("VOICEOVER_CUDA_LABEL", "CUDA GPU (auto-selected runtime)")
            self.compute_device.addItem(cuda_label, "cuda")
        saved_device = self.settings["compute_device"]
        if self.compute_device.findData(saved_device) < 0:
            saved_device = runtime_device
        self.compute_device.setCurrentIndex(max(0, self.compute_device.findData(saved_device)))
        self.preview_count = QSpinBox()
        self.preview_count.setRange(1, 2)
        self.preview_count.setValue(setting_int(self.settings, "preview_count"))
        self.cooldown_seconds = QSpinBox()
        self.cooldown_seconds.setRange(0, 60)
        self.cooldown_seconds.setValue(setting_int(self.settings, "cooldown_seconds"))
        self.reload_every = QSpinBox()
        self.reload_every.setRange(0, 200)
        self.reload_every.setValue(setting_int(self.settings, "reload_every"))
        self.reload_every.setSpecialValueText("Disabled")
        self.reload_every.setToolTip(
            "Reload OmniVoice periodically to reset accumulated CUDA memory. "
            "Existing output files are skipped automatically when resuming."
        )
        self.speaking_style = QComboBox()
        self.speaking_style.setEditable(True)
        self.speaking_style.addItems(
            [
                "Default cloned voice",
                "Warm, natural narration",
                "Calm documentary narration",
                "Energetic advertisement",
                "Dramatic cinematic narration",
                "Soft whisper",
                "Elderly, measured delivery",
                "Natural British English accent",
            ]
        )
        self.speaking_style.setCurrentText(self.settings["speaking_style"])
        self.speaking_style.setToolTip(
            "OmniVoice supports voice attributes such as elderly, low pitch, whisper, "
            "and british accent. Unsupported words are ignored safely."
        )
        self.use_speaking_style = QCheckBox("Enable OmniVoice speaking style / instruct")
        self.use_speaking_style.setChecked(setting_bool(self.settings, "use_speaking_style"))
        self.style_mode = QComboBox()
        self.style_mode.addItem("Apply direction to all segments", "global")
        self.style_mode.addItem("Auto per segment + base direction", "auto")
        self.style_mode.setCurrentIndex(max(0, self.style_mode.findData(self.settings["style_mode"])))
        self.merge_pause = QDoubleSpinBox()
        self.merge_pause.setRange(0, 10)
        self.merge_pause.setDecimals(2)
        self.merge_pause.setSingleStep(0.1)
        try:
            self.merge_pause.setValue(float(self.settings["merge_pause"]))
        except ValueError:
            self.merge_pause.setValue(0.45)
        self.merge_pause.setSuffix(" sec")
        self.merge_pause.setToolTip(
            "Silence inserted between each numbered voice-over file during merge."
        )
        self.progress = QProgressBar()
        self.status = QLabel("Ready")
        self.log = TranslatedLogEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(500)
        self.log.setPlaceholderText("Processing and model download status will appear here.")
        self.zonos2_progress = QProgressBar()
        self.zonos2_status = QLabel("Ready")
        self.zonos2_log = TranslatedLogEdit()
        self.zonos2_log.setReadOnly(True)
        self.zonos2_log.setMaximumBlockCount(500)
        self.zonos2_log.setPlaceholderText("ZONOS2 processing and server status will appear here.")
        self.hf_token = QLineEdit(self.settings["hf_token"])
        self.hf_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.hf_token.setPlaceholderText("Optional: required for gated/private Hugging Face models")
        self.gemini_key = QLineEdit(self.settings["gemini_api_key"])
        self.gemini_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.gemini_key.setPlaceholderText("Optional: reserved for future script-processing features")
        self.hf_home = QLineEdit(self.settings["hf_home"])
        self.hf_home.setPlaceholderText("Optional model cache folder; blank uses Hugging Face default")
        self.zonos2_server_url = QLineEdit(self.settings["zonos2_server_url"])
        self.zonos2_voice = QComboBox()
        self.zonos2_voice.setEditable(True)
        self.zonos2_voice.setPlaceholderText("Server default / no speaker conditioning")
        if self.settings["zonos2_voice_id"]:
            self.zonos2_voice.addItem(self.settings["zonos2_voice_id"], self.settings["zonos2_voice_id"])
            self.zonos2_voice.setCurrentText(self.settings["zonos2_voice_id"])
        self.zonos2_input_file = QLineEdit()
        self.zonos2_segment_text_input = QPlainTextEdit()
        self.zonos2_segment_text_input.setPlaceholderText(
            "Paste one or more segments here. Separate segments with a blank line."
        )
        self.zonos2_segment_text_input.setMaximumHeight(110)
        self.zonos2_output_dir = QLineEdit(self.settings["zonos2_output_dir"])
        self.zonos2_language = QComboBox()
        self.zonos2_language.addItem("Raw multilingual text (Vietnamese/Thai/etc.)", "raw")
        self.zonos2_language.addItem("English (US)", "en_us")
        self.zonos2_language.addItem("English (UK)", "en_gb")
        self.zonos2_language.addItem("French", "fr_fr")
        self.zonos2_language.addItem("German", "de")
        self.zonos2_language.addItem("Spanish", "es")
        self.zonos2_language.addItem("Italian", "it")
        self.zonos2_language.addItem("Portuguese (Brazil)", "pt_br")
        self.zonos2_language.addItem("Japanese", "ja")
        self.zonos2_language.addItem("Mandarin", "cmn")
        self.zonos2_language.addItem("Korean", "ko")
        self.zonos2_language.setCurrentIndex(
            max(0, self.zonos2_language.findData(self.settings["zonos2_language"]))
        )
        self.zonos2_speed = QDoubleSpinBox()
        self.zonos2_speed.setRange(0.5, 2.0)
        self.zonos2_speed.setSingleStep(0.05)
        self.zonos2_speed.setValue(float(self.settings["zonos2_speed"]))
        self.zonos2_seed = QSpinBox()
        self.zonos2_seed.setRange(0, 2147483647)
        self.zonos2_seed.setValue(setting_int(self.settings, "zonos2_seed"))
        self.zonos2_accurate_mode = QCheckBox("Accurate voice matching (off = expressive mode)")
        self.zonos2_accurate_mode.setChecked(setting_bool(self.settings, "zonos2_accurate_mode"))
        self.zonos2_clean_speaker_background = QCheckBox("Reference voice has clean background")
        self.zonos2_clean_speaker_background.setChecked(
            setting_bool(self.settings, "zonos2_clean_speaker_background")
        )
        self.zonos2_temperature = QDoubleSpinBox()
        self.zonos2_temperature.setRange(0.1, 3.0)
        self.zonos2_temperature.setSingleStep(0.05)
        self.zonos2_temperature.setValue(float(self.settings["zonos2_temperature"]))
        self.zonos2_topk = QSpinBox()
        self.zonos2_topk.setRange(0, 1000)
        self.zonos2_topk.setValue(setting_int(self.settings, "zonos2_topk"))
        self.zonos2_min_p = QDoubleSpinBox()
        self.zonos2_min_p.setRange(0.0, 1.0)
        self.zonos2_min_p.setSingleStep(0.01)
        self.zonos2_min_p.setValue(float(self.settings["zonos2_min_p"]))
        self.zonos2_repetition_penalty = QDoubleSpinBox()
        self.zonos2_repetition_penalty.setRange(1.0, 3.0)
        self.zonos2_repetition_penalty.setSingleStep(0.05)
        self.zonos2_repetition_penalty.setValue(float(self.settings["zonos2_repetition_penalty"]))
        self.zonos2_preview_count = QSpinBox()
        self.zonos2_preview_count.setRange(1, 2)
        self.zonos2_preview_count.setValue(setting_int(self.settings, "zonos2_preview_count"))
        self.zonos2_cooldown_seconds = QSpinBox()
        self.zonos2_cooldown_seconds.setRange(0, 60)
        self.zonos2_cooldown_seconds.setValue(setting_int(self.settings, "zonos2_cooldown_seconds"))
        self.zonos2_normalize_audio = QCheckBox("Normalize completed batch after all segments render")
        self.zonos2_normalize_audio.setChecked(setting_bool(self.settings, "zonos2_normalize_audio"))
        self.zonos2_merge_pause = QDoubleSpinBox()
        self.zonos2_merge_pause.setRange(0, 10)
        self.zonos2_merge_pause.setDecimals(2)
        self.zonos2_merge_pause.setValue(float(self.settings["zonos2_merge_pause"]))
        self.zonos2_merge_pause.setSuffix(" sec")
        self.zonos2_overwrite_existing = QCheckBox("Overwrite existing files in selected range")
        self.zonos2_range_from = QSpinBox()
        self.zonos2_range_from.setRange(1, 1)
        self.zonos2_range_to = QSpinBox()
        self.zonos2_range_to.setRange(1, 1)
        self.zonos2_output_format = QComboBox()
        self.zonos2_output_format.addItems(["wav", "mp3"])
        self.zonos2_output_format.setCurrentText(self.settings["zonos2_output_format"])

        self.video_effect_images_dir = QLineEdit(self.settings["video_effect_images_dir"])
        self.video_effect_audios_dir = QLineEdit(self.settings["video_effect_audios_dir"])
        self.video_effect_output_dir = QLineEdit(self.settings["video_effect_output_dir"])
        self.video_effect_aspect_ratio = QComboBox()
        self.video_effect_aspect_ratio.addItems(["16:9", "9:16", "2:3", "3:2"])
        self.video_effect_aspect_ratio.setCurrentText(self.settings["video_effect_aspect_ratio"])
        self.video_effect_quality = QComboBox()
        self.video_effect_quality.addItems(["HD", "FHD", "2K", "4K"])
        self.video_effect_quality.setCurrentText(self.settings["video_effect_quality"])
        self.video_effect_width = QSpinBox()
        self.video_effect_width.setRange(320, 7680)
        self.video_effect_width.setValue(setting_int(self.settings, "video_effect_width"))
        self.video_effect_width.setEnabled(False)
        self.video_effect_height = QSpinBox()
        self.video_effect_height.setRange(240, 4320)
        self.video_effect_height.setValue(setting_int(self.settings, "video_effect_height"))
        self.video_effect_height.setEnabled(False)
        self.video_effect_fps = QSpinBox()
        self.video_effect_fps.setRange(1, 120)
        self.video_effect_fps.setValue(setting_int(self.settings, "video_effect_fps"))
        self.video_effect_crf = QSpinBox()
        self.video_effect_crf.setRange(0, 40)
        self.video_effect_crf.setValue(setting_int(self.settings, "video_effect_crf"))
        self.video_effect_codec = QComboBox()
        self.video_effect_codec.addItems(["auto", "libx264", "h264_nvenc", "hevc_nvenc", "h264_qsv", "h264_amf"])
        self.video_effect_codec.setCurrentText(preferred_video_effect_codec(self.settings["video_effect_codec"]))
        self.video_effect_workers = QSpinBox()
        self.video_effect_workers.setRange(1, max(32, os.cpu_count() or 2))
        self.video_effect_workers.setValue(setting_int(self.settings, "video_effect_workers"))
        self.video_effect_pattern = QLineEdit(self.settings["video_effect_pattern"])
        self.video_effect_random_effects = QCheckBox("Random effects")
        self.video_effect_random_effects.setChecked(setting_bool(self.settings, "video_effect_random_effects"))
        self.video_effect_bounce = QCheckBox("Bounce motion")
        self.video_effect_bounce.setChecked(setting_bool(self.settings, "video_effect_bounce"))
        self.video_effect_merge = QCheckBox("Merge segment videos")
        self.video_effect_merge.setChecked(setting_bool(self.settings, "video_effect_merge"))
        self.video_effect_zoom_scale = QDoubleSpinBox()
        self.video_effect_zoom_scale.setRange(0.0, 2.0)
        self.video_effect_zoom_scale.setDecimals(3)
        self.video_effect_zoom_scale.setSingleStep(0.01)
        self.video_effect_zoom_scale.setValue(float(self.settings["video_effect_zoom_scale"]))
        self.video_effect_base_crop = QDoubleSpinBox()
        self.video_effect_base_crop.setRange(0.0, 0.50)
        self.video_effect_base_crop.setDecimals(3)
        self.video_effect_base_crop.setSingleStep(0.01)
        self.video_effect_base_crop.setValue(float(self.settings["video_effect_base_crop"]))
        self.video_effect_edge_reach = QDoubleSpinBox()
        self.video_effect_edge_reach.setRange(0.0, 1.0)
        self.video_effect_edge_reach.setDecimals(2)
        self.video_effect_edge_reach.setSingleStep(0.05)
        self.video_effect_edge_reach.setValue(float(self.settings["video_effect_edge_reach"]))
        self.video_effect_face_safe = QDoubleSpinBox()
        self.video_effect_face_safe.setRange(0.0, 5.0)
        self.video_effect_face_safe.setDecimals(2)
        self.video_effect_face_safe.setSingleStep(0.1)
        self.video_effect_face_safe.setValue(float(self.settings["video_effect_face_safe"]))
        self.video_effect_speed = QDoubleSpinBox()
        self.video_effect_speed.setRange(0.05, 5.0)
        self.video_effect_speed.setDecimals(2)
        self.video_effect_speed.setSingleStep(0.05)
        self.video_effect_speed.setValue(float(self.settings["video_effect_speed"]))
        self.video_effect_pre_silence = QDoubleSpinBox()
        self.video_effect_pre_silence.setRange(0.0, 10.0)
        self.video_effect_pre_silence.setDecimals(2)
        self.video_effect_pre_silence.setSingleStep(0.05)
        self.video_effect_pre_silence.setValue(float(self.settings["video_effect_pre_silence"]))
        self.video_effect_min_motion = QDoubleSpinBox()
        self.video_effect_min_motion.setRange(0.0, 0.5)
        self.video_effect_min_motion.setDecimals(3)
        self.video_effect_min_motion.setSingleStep(0.001)
        self.video_effect_min_motion.setValue(float(self.settings["video_effect_min_motion"]))
        self.video_effect_combo_radius = QDoubleSpinBox()
        self.video_effect_combo_radius.setRange(0.0, 2.0)
        self.video_effect_combo_radius.setDecimals(3)
        self.video_effect_combo_radius.setSingleStep(0.01)
        self.video_effect_combo_radius.setValue(float(self.settings["video_effect_combo_radius"]))
        self.video_effect_combo_offset_x = QDoubleSpinBox()
        self.video_effect_combo_offset_x.setRange(-2.0, 2.0)
        self.video_effect_combo_offset_x.setDecimals(3)
        self.video_effect_combo_offset_x.setSingleStep(0.01)
        self.video_effect_combo_offset_x.setValue(float(self.settings["video_effect_combo_offset_x"]))
        self.video_effect_combo_offset_y = QDoubleSpinBox()
        self.video_effect_combo_offset_y.setRange(-2.0, 2.0)
        self.video_effect_combo_offset_y.setDecimals(3)
        self.video_effect_combo_offset_y.setSingleStep(0.01)
        self.video_effect_combo_offset_y.setValue(float(self.settings["video_effect_combo_offset_y"]))
        try:
            motion_templates = json.loads(self.settings["video_effect_motion_templates"])
            self.video_effect_motion_templates = (
                motion_templates if isinstance(motion_templates, dict) else {}
            )
        except (TypeError, ValueError):
            self.video_effect_motion_templates = {}
        self.video_effect_motion_template = QComboBox()
        self.refresh_video_effect_motion_templates(
            self.settings.get("video_effect_motion_template", "Basic Motion")
        )
        self.video_effect_retro_preset = QComboBox()
        self.video_effect_retro_preset.addItems(["Off", "Subtle", "Medium", "Heavy", "Custom"])
        self.video_effect_retro_preset.setCurrentText(self.settings["video_effect_retro_preset"])
        self.video_effect_retro_scratches_enabled = QCheckBox("Scratches")
        self.video_effect_retro_scratches_enabled.setChecked(
            setting_bool(self.settings, "video_effect_retro_scratches_enabled")
        )
        self.video_effect_retro_scratch = QDoubleSpinBox()
        self.video_effect_retro_scratch.setRange(0.0, 1.0)
        self.video_effect_retro_scratch.setDecimals(2)
        self.video_effect_retro_scratch.setSingleStep(0.05)
        self.video_effect_retro_scratch.setValue(float(self.settings["video_effect_retro_scratch"]))
        self.video_effect_retro_dust_enabled = QCheckBox("Dust specks")
        self.video_effect_retro_dust_enabled.setChecked(
            setting_bool(self.settings, "video_effect_retro_dust_enabled")
        )
        self.video_effect_retro_dust = QDoubleSpinBox()
        self.video_effect_retro_dust.setRange(0.0, 1.0)
        self.video_effect_retro_dust.setDecimals(2)
        self.video_effect_retro_dust.setSingleStep(0.05)
        self.video_effect_retro_dust.setValue(float(self.settings["video_effect_retro_dust"]))
        self.video_effect_retro_grain_enabled = QCheckBox("Film grain")
        self.video_effect_retro_grain_enabled.setChecked(
            setting_bool(self.settings, "video_effect_retro_grain_enabled")
        )
        self.video_effect_retro_grain = QDoubleSpinBox()
        self.video_effect_retro_grain.setRange(0.0, 1.0)
        self.video_effect_retro_grain.setDecimals(2)
        self.video_effect_retro_grain.setSingleStep(0.05)
        self.video_effect_retro_grain.setValue(float(self.settings["video_effect_retro_grain"]))
        self.video_effect_retro_flicker_enabled = QCheckBox("Flicker")
        self.video_effect_retro_flicker_enabled.setChecked(
            setting_bool(self.settings, "video_effect_retro_flicker_enabled")
        )
        self.video_effect_retro_flicker = QDoubleSpinBox()
        self.video_effect_retro_flicker.setRange(0.0, 0.25)
        self.video_effect_retro_flicker.setDecimals(2)
        self.video_effect_retro_flicker.setSingleStep(0.01)
        self.video_effect_retro_flicker.setValue(float(self.settings["video_effect_retro_flicker"]))
        self.video_effect_retro_vignette_enabled = QCheckBox("Vignette")
        self.video_effect_retro_vignette_enabled.setChecked(
            setting_bool(self.settings, "video_effect_retro_vignette_enabled")
        )
        self.video_effect_retro_vignette = QDoubleSpinBox()
        self.video_effect_retro_vignette.setRange(0.0, 1.0)
        self.video_effect_retro_vignette.setDecimals(2)
        self.video_effect_retro_vignette.setSingleStep(0.05)
        self.video_effect_retro_vignette.setValue(float(self.settings["video_effect_retro_vignette"]))
        self.video_effect_retro_color_fade_enabled = QCheckBox("Color fade")
        self.video_effect_retro_color_fade_enabled.setChecked(
            setting_bool(self.settings, "video_effect_retro_color_fade_enabled")
        )
        self.video_effect_retro_color_fade = QDoubleSpinBox()
        self.video_effect_retro_color_fade.setRange(0.0, 1.0)
        self.video_effect_retro_color_fade.setDecimals(2)
        self.video_effect_retro_color_fade.setSingleStep(0.05)
        self.video_effect_retro_color_fade.setValue(float(self.settings["video_effect_retro_color_fade"]))
        self.video_effect_retro_scan_lines_enabled = QCheckBox("Scan lines")
        self.video_effect_retro_scan_lines_enabled.setChecked(
            setting_bool(self.settings, "video_effect_retro_scan_lines_enabled")
        )
        self.video_effect_retro_scan_lines = QDoubleSpinBox()
        self.video_effect_retro_scan_lines.setRange(0.0, 1.0)
        self.video_effect_retro_scan_lines.setDecimals(2)
        self.video_effect_retro_scan_lines.setSingleStep(0.05)
        self.video_effect_retro_scan_lines.setValue(float(self.settings["video_effect_retro_scan_lines"]))
        self.video_effect_progress = QProgressBar()
        self.video_effect_status = QLabel("Ready")
        self.video_effect_log = TranslatedLogEdit()
        self.video_effect_log.setReadOnly(True)
        self.video_effect_log.setMaximumBlockCount(1000)
        self.video_effect_log.setPlaceholderText("Video Effect render log will appear here.")
        self.create_caption_widgets()
        self.create_watermark_widgets()
        self.create_tools_widgets()

        self.save_profile_button = self.button("Save voice profile", self.save_profile)
        self.save_profile_button.setToolTip(
            "Enter a new profile name to create a voice, or leave it blank to overwrite only "
            "the transcript of the selected saved voice."
        )
        self.import_piper_button = self.button(
            "Create clone voices from tts-model", self.import_piper_profiles
        )
        clone_form = QFormLayout()
        saved_voice_widget = QWidget()
        saved_voice_layout = QHBoxLayout(saved_voice_widget)
        saved_voice_layout.setContentsMargins(0, 0, 0, 0)
        saved_voice_layout.setSpacing(8)
        saved_voice_layout.addWidget(self.profile, 1)
        self.preview_voice_button = self.button("Preview voice", self.preview_selected_voice)
        self.preview_voice_button.setToolTip("Play or stop the selected voice's reference audio.")
        self.delete_voice_button = self.button("Delete voice", self.delete_selected_voice)
        self.delete_voice_button.setToolTip("Permanently delete the selected voice profile.")
        saved_voice_layout.addWidget(self.preview_voice_button)
        saved_voice_layout.addWidget(self.delete_voice_button)
        clone_form.addRow("Saved voice", saved_voice_widget)
        clone_form.addRow("Reference language", self.clone_language)
        clone_form.addRow("New profile name", self.profile_name)
        clone_form.addRow("Reference MP3/WAV", self.with_browse(self.reference_audio, self.pick_audio))
        transcript_widget = QWidget()
        transcript_layout = QHBoxLayout(transcript_widget)
        transcript_layout.setContentsMargins(0, 0, 0, 0)
        transcript_layout.setSpacing(8)
        transcript_layout.addWidget(self.reference_text, 1)
        self.auto_transcript_button = self.button(
            "Auto transcript", self.auto_transcribe_selected_voice
        )
        self.auto_transcript_button.setToolTip(
            "Use Whisper to transcribe the selected voice reference audio and fill this text box."
        )
        transcript_layout.addWidget(
            self.auto_transcript_button, 0, Qt.AlignmentFlag.AlignTop
        )
        clone_form.addRow("Reference transcript", transcript_widget)
        clone_form.addRow("", self.save_profile_button)
        clone_form.addRow("", self.import_piper_button)

        self.voice_list_progress = QProgressBar()
        self.voice_list_progress.setRange(0, 100)
        self.voice_list_progress.setValue(0)
        self.voice_list_status = QLabel("Ready")
        self.voice_list_log = TranslatedLogEdit()
        self.voice_list_log.setReadOnly(True)
        self.voice_list_log.setMaximumBlockCount(1000)
        self.voice_list_log.setMinimumHeight(120)
        self.voice_list_log.setPlaceholderText(
            "Voice profile and transcript progress will appear here."
        )
        voice_list_progress_group = QGroupBox("Voice List Progress")
        voice_list_progress_layout = QVBoxLayout(voice_list_progress_group)
        voice_list_progress_layout.addWidget(self.voice_list_progress)
        voice_list_progress_layout.addWidget(self.voice_list_status)
        voice_list_progress_layout.addWidget(self.voice_list_log, 1)

        profile_manager = QWidget()
        profile_manager_layout = QVBoxLayout(profile_manager)
        profile_manager_layout.setContentsMargins(4, 4, 4, 4)
        profile_manager_layout.addLayout(clone_form)
        profile_manager_layout.addStretch()

        self.voice_design_source = QComboBox()
        self.voice_design_name = QLineEdit()
        self.voice_design_name.setPlaceholderText("Required: a new, unique profile name")
        self.voice_design_preset = QComboBox()
        self.voice_design_preset.addItems(
            ["Subtle variation", "Warm and deeper", "Bright and younger", "Calm and soft", "Custom"]
        )
        self.voice_design_gender_lock = QCheckBox("Keep the variation within the same-gender range")
        self.voice_design_gender_lock.setChecked(True)
        self.voice_design_pitch = QDoubleSpinBox()
        self.voice_design_pitch.setRange(-1.5, 1.5)
        self.voice_design_pitch.setDecimals(1)
        self.voice_design_pitch.setSingleStep(0.2)
        self.voice_design_pitch.setSuffix(" st")
        self.voice_design_formant = QDoubleSpinBox()
        self.voice_design_formant.setRange(-2.0, 2.0)
        self.voice_design_formant.setDecimals(1)
        self.voice_design_formant.setSingleStep(0.2)
        self.voice_design_formant.setSuffix(" tone")
        self.voice_design_warmth = QDoubleSpinBox()
        self.voice_design_warmth.setRange(-6.0, 6.0)
        self.voice_design_warmth.setDecimals(1)
        self.voice_design_warmth.setSingleStep(0.5)
        self.voice_design_warmth.setSuffix(" dB")
        self.voice_design_brightness = QDoubleSpinBox()
        self.voice_design_brightness.setRange(-6.0, 6.0)
        self.voice_design_brightness.setDecimals(1)
        self.voice_design_brightness.setSingleStep(0.5)
        self.voice_design_brightness.setSuffix(" dB")
        self.voice_design_speed = QDoubleSpinBox()
        self.voice_design_speed.setRange(0.85, 1.15)
        self.voice_design_speed.setDecimals(2)
        self.voice_design_speed.setSingleStep(0.01)
        self.voice_design_speed.setValue(1.0)
        self.voice_design_speed.setSuffix("x")

        designer_form = QFormLayout()
        designer_form.addRow("Source voice", self.voice_design_source)
        designer_form.addRow("New profile name", self.voice_design_name)
        designer_form.addRow("Preset", self.voice_design_preset)
        designer_form.addRow("Gender range", self.voice_design_gender_lock)
        designer_form.addRow("Pitch shift", self.voice_design_pitch)
        designer_form.addRow("Timbre / resonance", self.voice_design_formant)
        designer_form.addRow("Warmth", self.voice_design_warmth)
        designer_form.addRow("Brightness", self.voice_design_brightness)
        designer_form.addRow("Speaking speed", self.voice_design_speed)

        self.voice_design_play_original_button = self.button(
            "Play original", self.play_voice_design_original
        )
        self.voice_design_generate_button = self.button(
            "Generate preview", self.generate_voice_design_preview
        )
        self.voice_design_play_preview_button = self.button(
            "Play preview", self.play_voice_design_preview
        )
        self.voice_design_reset_button = self.button(
            "Reset", self.reset_voice_design_controls
        )
        self.voice_design_save_button = self.button(
            "Save as new profile", self.save_voice_design_profile
        )
        self.voice_design_play_preview_button.setEnabled(False)
        self.voice_design_save_button.setEnabled(False)
        designer_actions = QHBoxLayout()
        designer_actions.addWidget(self.voice_design_play_original_button)
        designer_actions.addWidget(self.voice_design_generate_button)
        designer_actions.addWidget(self.voice_design_play_preview_button)
        designer_actions.addWidget(self.voice_design_reset_button)
        designer_actions.addWidget(self.voice_design_save_button)

        designer_note = QLabel(
            "Natural mode uses one formant-preserving pass plus gentle tone EQ. Keep Gender "
            "lock enabled; small adjustments sound substantially more realistic."
        )
        designer_note.setWordWrap(True)
        voice_designer = QWidget()
        voice_designer_layout = QVBoxLayout(voice_designer)
        voice_designer_layout.addWidget(designer_note)
        voice_designer_layout.addLayout(designer_form)
        voice_designer_layout.addLayout(designer_actions)
        voice_designer_layout.addStretch()

        self.voice_list_subtabs = QTabWidget()
        self.voice_list_subtabs.addTab(profile_manager, "Profile Manager")
        self.voice_list_subtabs.addTab(voice_designer, "Voice Designer")
        clone_tab = QWidget()
        clone_layout = QVBoxLayout(clone_tab)
        clone_layout.addWidget(self.voice_list_subtabs, 1)
        clone_layout.addWidget(voice_list_progress_group)

        self.voice_design_preview_path: Path | None = None
        self.voice_design_preview_signature = ""
        self.voice_design_pending_signature = ""
        self.voice_design_preset.currentTextChanged.connect(self.apply_voice_design_preset)
        self.voice_design_gender_lock.toggled.connect(self.update_voice_design_gender_range)
        self.voice_design_source.currentIndexChanged.connect(self.invalidate_voice_design_preview)
        for control in (
            self.voice_design_pitch,
            self.voice_design_formant,
            self.voice_design_warmth,
            self.voice_design_brightness,
            self.voice_design_speed,
        ):
            control.valueChanged.connect(self.invalidate_voice_design_preview)
        self.apply_voice_design_preset(self.voice_design_preset.currentText())

        voice_form = QFormLayout()
        voice_language_widget = QWidget()
        voice_language_layout = QHBoxLayout(voice_language_widget)
        voice_language_layout.setContentsMargins(0, 0, 0, 0)
        voice_language_layout.setSpacing(8)
        voice_language_layout.addWidget(self.voice_profile, 2)
        self.default_voice_profile_button = self.button("Set default", self.set_default_voice_profile)
        self.default_voice_profile_button.setToolTip(
            "Save this voice as the default Voice Clone profile for the next app launch."
        )
        voice_language_layout.addWidget(self.default_voice_profile_button)
        voice_language_layout.addWidget(QLabel("Language"))
        voice_language_layout.addWidget(self.language, 1)
        voice_form.addRow("Voice profile", voice_language_widget)
        voice_group = QGroupBox("Voice and Input")
        voice_group.setLayout(voice_form)

        self.batch_container = QWidget()
        self.batch_layout = QVBoxLayout(self.batch_container)
        self.batch_layout.setContentsMargins(4, 4, 4, 4)
        self.batch_layout.setSpacing(6)
        
        self.batch_scroll = QScrollArea()
        self.batch_scroll.setWidgetResizable(True)
        self.batch_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.batch_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.batch_scroll.setWidget(self.batch_container)
        
        self.add_row_btn = self.button("+ Add Task Row", self.add_batch_row_clicked)
        
        batch_group_layout = QVBoxLayout()
        batch_group_layout.addWidget(self.batch_scroll)
        batch_group_layout.addWidget(self.add_row_btn)
        
        self.batch_group = QGroupBox("Batch Processing Queue")
        self.batch_group.setLayout(batch_group_layout)

        generation_form = QFormLayout()
        model_widget = QWidget()
        model_layout = QHBoxLayout(model_widget)
        model_layout.setContentsMargins(0, 0, 0, 0)
        model_layout.setSpacing(8)
        model_layout.addWidget(self.model_name, 2)
        model_layout.addWidget(QLabel("Diffusion steps"))
        model_layout.addWidget(self.steps, 1)
        generation_form.addRow("Checkpoint", model_widget)
        generation_form.addRow("Compute device", self.compute_device)
        generation_form.addRow("Preview segments", self.preview_count)
        stability_widget = QWidget()
        stability_layout = QHBoxLayout(stability_widget)
        stability_layout.setContentsMargins(0, 0, 0, 0)
        stability_layout.setSpacing(8)
        stability_layout.addWidget(QLabel("Cooldown"))
        stability_layout.addWidget(self.cooldown_seconds)
        stability_layout.addWidget(QLabel("Reload every N segments"))
        stability_layout.addWidget(self.reload_every)
        generation_form.addRow("Stability", stability_widget)
        generation_form.addRow(QLabel(""), self.use_speaking_style)
        generation_form.addRow("Voice style", self.speaking_style)
        generation_form.addRow("Direction mode", self.style_mode)
        direction_actions = QHBoxLayout()
        direction_actions.addWidget(self.button("Set for selected", self.set_selected_segment_style))
        direction_actions.addWidget(self.button("Clear selected", self.clear_selected_segment_style))
        generation_form.addRow("Segment override", direction_actions)
        generation_form.addRow(QLabel(""), self.fit_timeline)
        generation_group = QGroupBox("OmniVoice Configuration")
        generation_group.setLayout(generation_form)

        output_form = QFormLayout()
        format_pause_widget = QWidget()
        format_pause_layout = QHBoxLayout(format_pause_widget)
        format_pause_layout.setContentsMargins(0, 0, 0, 0)
        format_pause_layout.setSpacing(8)
        format_pause_layout.addWidget(self.output_format, 1)
        format_pause_layout.addWidget(QLabel("Merge pause"))
        format_pause_layout.addWidget(self.merge_pause, 1)
        output_form.addRow("Output format", format_pause_widget)
        output_form.addRow(QLabel(""), self.normalize_audio)
        self.retry_normalize_button = self.button(
            "Retry batch normalization", self.retry_batch_normalization
        )
        self.retry_normalize_button.setToolTip(
            "Run only the completed-batch loudness pass again after closing an audio player "
            "that locked one of the voice-over files."
        )
        output_form.addRow(QLabel(""), self.retry_normalize_button)
        output_group = QGroupBox("Output and Audio")
        output_group.setLayout(output_form)

        self.render_range_button = self.button("Render selected range", self.render_range)
        range_form = QFormLayout()
        range_widget = QWidget()
        range_layout = QHBoxLayout(range_widget)
        range_layout.setContentsMargins(0, 0, 0, 0)
        range_layout.addWidget(QLabel("From"))
        range_layout.addWidget(self.range_from)
        range_layout.addWidget(QLabel("To"))
        range_layout.addWidget(self.range_to)
        range_form.addRow("Segments", range_widget)
        range_form.addRow(QLabel(""), self.overwrite_existing)
        range_form.addRow(QLabel(""), self.render_range_button)
        range_group = QGroupBox("Render Range")
        range_group.setLayout(range_form)

        for form in (voice_form, generation_form, output_form, range_form):
            self.align_left_form(form)

        left_panel = QWidget()
        left_panel.setMinimumWidth(560)
        left_panel.setMaximumWidth(580)
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(voice_group)
        left_layout.addWidget(self.batch_group)
        left_layout.addWidget(output_group)
        left_layout.addWidget(generation_group)
        left_layout.addWidget(range_group)
        settings_actions = QHBoxLayout()
        settings_actions.addWidget(self.button("Save Settings", self.save_voice_clone_settings))
        settings_actions.addWidget(self.button("Load defaults", self.load_defaults))
        left_layout.addLayout(settings_actions)
        left_layout.addStretch()

        self.segment_table = QTableWidget(0, 6)
        self.segment_table.setHorizontalHeaderLabels(
            ["#", "Time", "Text", "Status", "Direction", "Actions"]
        )
        self.segment_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.segment_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.segment_table.setWordWrap(True)
        self.segment_table.verticalHeader().setVisible(False)
        self.segment_table.verticalHeader().setDefaultSectionSize(72)
        header = self.segment_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        header.resizeSection(4, 170)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.addWidget(QLabel("Voice-over segments"))
        right_layout.addWidget(self.segment_text_input)
        self.add_omnivoice_segments_button = self.button(
            "Add text segments", self.add_omnivoice_text_segments
        )
        right_layout.addWidget(self.add_omnivoice_segments_button)
        right_layout.addWidget(self.segment_table)
        right_layout.addWidget(self.progress)
        right_layout.addWidget(self.status)
        self.log.setMaximumHeight(120)
        right_layout.addWidget(self.log)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([560, 720])

        self.render_button = self.button("Render all segments", self.render)
        self.preview_button = self.button("Render preview", self.render_preview)
        self.merge_button = self.button("Merge numbered audio files", self.merge_audio)
        self.stop_button = self.button("Stop current render", self.stop_current_render)
        self.open_output_button = self.button("Open output folder", self.open_output_folder)
        self.stop_button.setEnabled(False)
        action_row = QHBoxLayout()
        action_row.addWidget(self.preview_button)
        action_row.addWidget(self.render_button)
        action_row.addWidget(self.stop_button)
        action_row.addWidget(self.merge_button)
        action_row.addWidget(self.open_output_button)
        voice_over_tab = QWidget()
        voice_over_layout = QVBoxLayout(voice_over_tab)
        voice_over_layout.addWidget(splitter)
        voice_over_layout.addLayout(action_row)

        settings_tab = QWidget()
        settings_page_layout = QVBoxLayout(settings_tab)

        license_form = QFormLayout()
        self.license_status_value = QLabel()
        self.license_status_value.setStyleSheet("color: #65e6a7; font-weight: 700;")
        self.license_request_value = QLineEdit()
        self.license_request_value.setReadOnly(True)
        self.license_request_value.setStyleSheet("font-family: Consolas;")
        self.license_copy_button = self.button("Copy", self.copy_license_request_id)
        license_request_row = QWidget()
        license_request_layout = QHBoxLayout(license_request_row)
        license_request_layout.setContentsMargins(0, 0, 0, 0)
        license_request_layout.addWidget(self.license_request_value, 1)
        license_request_layout.addWidget(self.license_copy_button)
        self.license_expiry_value = QLabel()
        self.license_remaining_value = QLabel()
        license_form.addRow("License status", self.license_status_value)
        license_form.addRow("Request ID", license_request_row)
        license_form.addRow("Expiration date", self.license_expiry_value)
        license_form.addRow("Time remaining", self.license_remaining_value)
        license_group = QGroupBox("License Information")
        license_group.setLayout(license_form)
        settings_page_layout.addWidget(license_group)

        settings_form = QFormLayout()
        settings_form.addRow("HF token", self.hf_token)
        settings_form.addRow("Gemini API key", self.gemini_key)
        settings_form.addRow("Model cache", self.with_browse(self.hf_home, self.pick_cache))
        settings_actions = QWidget()
        settings_actions_layout = QHBoxLayout(settings_actions)
        settings_actions_layout.setContentsMargins(0, 0, 0, 0)
        settings_actions_layout.setSpacing(8)
        settings_actions_layout.addWidget(
            self.button("Save settings", self.save_environment_settings), 1
        )
        settings_actions_layout.addWidget(
            self.button("Open persistent log folder", self.open_log_folder), 1
        )
        settings_form.addRow("", settings_actions)
        environment_settings_group = QGroupBox("Settings")
        environment_settings_group.setLayout(settings_form)
        settings_page_layout.addWidget(environment_settings_group)
        settings_page_layout.addStretch()

        zonos2_connection_form = QFormLayout()
        zonos2_connection_form.addRow("Checkpoint", QLabel(DEFAULT_ZONOS2_MODEL))
        zonos2_connection_form.addRow("Server", self.zonos2_server_url)
        zonos2_voice_widget = QWidget()
        zonos2_voice_layout = QHBoxLayout(zonos2_voice_widget)
        zonos2_voice_layout.setContentsMargins(0, 0, 0, 0)
        zonos2_voice_layout.setSpacing(8)
        zonos2_voice_layout.addWidget(self.zonos2_voice, 1)
        zonos2_voice_layout.addWidget(self.button("Refresh", self.refresh_zonos2_voices))
        zonos2_connection_form.addRow("Voice", zonos2_voice_widget)
        zonos2_connection_form.addRow(
            "SRT/TXT input", self.with_browse(self.zonos2_input_file, self.pick_zonos2_input)
        )
        zonos2_connection_group = QGroupBox("Zonos2 Server, Voice and Input")
        zonos2_connection_group.setLayout(zonos2_connection_form)

        zonos2_generation_form = QFormLayout()
        zonos2_generation_form.addRow(
            "Language",
            self.paired_controls(self.zonos2_language, "Speed", self.zonos2_speed),
        )
        zonos2_generation_form.addRow("Seed", self.zonos2_seed)
        zonos2_generation_form.addRow(QLabel(""), self.zonos2_accurate_mode)
        zonos2_generation_form.addRow(
            "Temperature",
            self.paired_controls(self.zonos2_temperature, "Top-k", self.zonos2_topk),
        )
        zonos2_generation_form.addRow(
            "Min-p",
            self.paired_controls(self.zonos2_min_p, "Penalty", self.zonos2_repetition_penalty),
        )
        zonos2_generation_form.addRow(QLabel(""), self.zonos2_clean_speaker_background)
        zonos2_generation_group = QGroupBox("Zonos2 Generation")
        zonos2_generation_group.setLayout(zonos2_generation_form)

        zonos2_output_form = QFormLayout()
        zonos2_output_form.addRow(
            "Output folder", self.with_browse(self.zonos2_output_dir, self.pick_zonos2_output)
        )
        zonos2_output_form.addRow(
            "Preview",
            self.paired_controls(self.zonos2_preview_count, "Cooldown", self.zonos2_cooldown_seconds),
        )
        zonos2_output_form.addRow(
            "Format",
            self.paired_controls(self.zonos2_output_format, "Merge pause", self.zonos2_merge_pause),
        )
        zonos2_output_form.addRow(QLabel(""), self.zonos2_normalize_audio)
        zonos2_range_widget = QWidget()
        zonos2_range_layout = QHBoxLayout(zonos2_range_widget)
        zonos2_range_layout.setContentsMargins(0, 0, 0, 0)
        zonos2_range_layout.addWidget(QLabel("From"))
        zonos2_range_layout.addWidget(self.zonos2_range_from)
        zonos2_range_layout.addWidget(QLabel("To"))
        zonos2_range_layout.addWidget(self.zonos2_range_to)
        zonos2_output_form.addRow("Render range", zonos2_range_widget)
        zonos2_output_form.addRow(QLabel(""), self.zonos2_overwrite_existing)
        zonos2_notice = QLabel(
            "ZONOS2 runs on a separate Linux/WSL server. Start it with checkpoint "
            "Zyphra/ZONOS2 on port 1919. Refresh and select a server voice before rendering."
        )
        zonos2_notice.setWordWrap(True)
        self.zonos2_preview_button = self.button("Render preview", self.render_zonos2_preview)
        self.zonos2_range_button = self.button("Render selected range", self.render_zonos2_range)
        self.zonos2_render_button = self.button("Render all segments", self.start_zonos2)
        self.zonos2_stop_button = self.button("Stop ZONOS2 render", self.stop_current_render)
        self.zonos2_merge_button = self.button("Merge numbered audio files", self.merge_zonos2_audio)
        self.zonos2_open_output_button = self.button("Open output folder", self.open_zonos2_output_folder)
        self.zonos2_stop_button.setEnabled(False)
        zonos2_output_form.addRow(QLabel(""), self.zonos2_range_button)
        zonos2_output_group = QGroupBox("Zonos2 Output and Range")
        zonos2_output_group.setLayout(zonos2_output_form)
        for form in (zonos2_connection_form, zonos2_generation_form, zonos2_output_form):
            self.align_left_form(form)
        zonos2_settings_actions = QHBoxLayout()
        self.zonos2_save_settings_button = self.button("Save Settings", self.save_voice_clone_settings)
        self.zonos2_load_defaults_button = self.button("Load defaults", self.load_defaults)
        zonos2_settings_actions.addWidget(self.zonos2_save_settings_button, 1)
        zonos2_settings_actions.addWidget(self.zonos2_load_defaults_button, 1)
        zonos2_left_panel = QWidget()
        zonos2_left_panel.setMinimumWidth(560)
        zonos2_left_panel.setMaximumWidth(580)
        zonos2_left_layout = QVBoxLayout(zonos2_left_panel)
        zonos2_left_layout.addWidget(zonos2_notice)
        zonos2_left_layout.addWidget(zonos2_connection_group)
        zonos2_left_layout.addWidget(zonos2_generation_group)
        zonos2_left_layout.addWidget(zonos2_output_group)
        zonos2_left_layout.addLayout(zonos2_settings_actions)
        zonos2_left_layout.addStretch()

        self.zonos2_segment_table = QTableWidget(0, 5)
        self.zonos2_segment_table.setHorizontalHeaderLabels(
            ["#", "Time", "Text", "Status", "Actions"]
        )
        self.zonos2_segment_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.zonos2_segment_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.zonos2_segment_table.setWordWrap(True)
        self.zonos2_segment_table.verticalHeader().setVisible(False)
        self.zonos2_segment_table.verticalHeader().setDefaultSectionSize(72)
        zonos2_header = self.zonos2_segment_table.horizontalHeader()
        zonos2_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        zonos2_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        zonos2_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        zonos2_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        zonos2_header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        zonos2_right_panel = QWidget()
        zonos2_right_layout = QVBoxLayout(zonos2_right_panel)
        zonos2_right_layout.addWidget(QLabel("ZONOS2 voice-over segments"))
        zonos2_right_layout.addWidget(self.zonos2_segment_text_input)
        self.add_zonos2_segments_button = self.button(
            "Add text segments", self.add_zonos2_text_segments
        )
        zonos2_right_layout.addWidget(self.add_zonos2_segments_button)
        zonos2_right_layout.addWidget(self.zonos2_segment_table)
        zonos2_right_layout.addWidget(self.zonos2_progress)
        zonos2_right_layout.addWidget(self.zonos2_status)
        self.zonos2_log.setMaximumHeight(120)
        zonos2_right_layout.addWidget(self.zonos2_log)

        zonos2_splitter = QSplitter(Qt.Orientation.Horizontal)
        zonos2_splitter.addWidget(zonos2_left_panel)
        zonos2_splitter.addWidget(zonos2_right_panel)
        zonos2_splitter.setSizes([560, 720])
        zonos2_tab = QWidget()
        self.zonos2_tab = zonos2_tab
        zonos2_layout = QVBoxLayout(zonos2_tab)
        zonos2_layout.addWidget(zonos2_splitter)
        zonos2_action_row = QHBoxLayout()
        zonos2_action_row.addWidget(self.zonos2_preview_button)
        zonos2_action_row.addWidget(self.zonos2_render_button)
        zonos2_action_row.addWidget(self.zonos2_stop_button)
        zonos2_action_row.addWidget(self.zonos2_merge_button)
        zonos2_action_row.addWidget(self.zonos2_open_output_button)
        zonos2_layout.addLayout(zonos2_action_row)

        self.video_effect_batch_container = QWidget()
        self.video_effect_batch_layout = QVBoxLayout(self.video_effect_batch_container)
        self.video_effect_batch_layout.setContentsMargins(0, 0, 0, 0)
        self.video_effect_batch_layout.setSpacing(8)
        self.video_effect_batch_scroll = QScrollArea()
        self.video_effect_batch_scroll.setWidgetResizable(True)
        self.video_effect_batch_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.video_effect_batch_scroll.setWidget(self.video_effect_batch_container)
        self.add_video_effect_batch_row(
            self.video_effect_images_dir.text(),
            self.video_effect_audios_dir.text(),
            self.video_effect_output_dir.text(),
            primary=True,
        )
        video_effect_input_layout = QVBoxLayout()
        video_effect_input_layout.addWidget(self.video_effect_batch_scroll)
        video_effect_input_actions = QHBoxLayout()
        video_effect_input_actions.addWidget(
            self.button("+ Add Images / Audios / Output", self.add_video_effect_batch_row_clicked)
        )
        check_images_button = self.button(
            "Check Images Folder", self.check_video_effect_image_folders
        )
        check_images_button.setToolTip(
            "Tìm số thứ tự trong tên file hình của từng batch và báo số thiếu/trùng trong log."
        )
        check_images_button.setStyleSheet(
            "QPushButton { background: #12323a; border: 1px solid #21b6cf; color: #d9faff; }"
            "QPushButton:hover { background: #19434d; }"
        )
        video_effect_input_actions.addWidget(check_images_button)
        video_effect_output_actions = QHBoxLayout()
        self.video_effect_check_videos_button = self.button(
            "Check Video Output", self.check_video_effect_video_folders
        )
        self.video_effect_check_videos_button.setToolTip(
            "Kiểm tra số thứ tự và giải mã từng video trong Output để phát hiện file bị lỗi."
        )
        self.video_effect_check_videos_button.setStyleSheet(
            "QPushButton { background: #352712; border: 1px solid #d69a32; color: #ffe8b5; }"
            "QPushButton:hover { background: #493619; }"
        )
        video_effect_output_actions.addWidget(self.video_effect_check_videos_button)
        self.video_effect_merge_output_button = self.button(
            "Merge Video Output", self.merge_video_effect_output_folders
        )
        self.video_effect_merge_output_button.setToolTip(
            "Ghép các video nằm trực tiếp trong Output theo thứ tự tên; bỏ qua thư mục con "
            "và lưu kết quả vào một thư mục con mới."
        )
        self.video_effect_merge_output_button.setStyleSheet(
            "QPushButton { background: #352712; border: 1px solid #d69a32; color: #ffe8b5; }"
            "QPushButton:hover { background: #493619; }"
        )
        video_effect_output_actions.addWidget(self.video_effect_merge_output_button)
        video_effect_input_layout.addLayout(video_effect_input_actions)
        video_effect_input_layout.addLayout(video_effect_output_actions)
        video_effect_input_group = QGroupBox("Input and Output")
        video_effect_input_group.setLayout(video_effect_input_layout)

        video_effect_render_form = QFormLayout()
        video_effect_render_form.addRow(
            "Frame",
            self.paired_controls(
                self.video_effect_aspect_ratio, "Quality", self.video_effect_quality
            ),
        )
        video_effect_render_form.addRow(
            "Size",
            self.paired_controls(self.video_effect_width, "Height", self.video_effect_height),
        )
        video_effect_render_form.addRow(
            "FPS",
            self.paired_controls(self.video_effect_fps, "CRF", self.video_effect_crf),
        )
        video_effect_render_form.addRow(
            "Codec",
            self.paired_controls(self.video_effect_codec, "Workers", self.video_effect_workers),
        )
        video_effect_render_form.addRow("Pattern", self.video_effect_pattern)
        video_effect_render_form.addRow(QLabel(""), self.video_effect_random_effects)
        video_effect_render_form.addRow(QLabel(""), self.video_effect_bounce)
        video_effect_render_form.addRow(QLabel(""), self.video_effect_merge)
        self.set_form_tooltips(
            video_effect_render_form,
            {
                "Frame": (
                    "Chọn tỉ lệ khung hình xuất video. Ảnh sẽ được crop để đúng tỉ lệ đã chọn, "
                    "ví dụ 16:9 ngang, 9:16 dọc, 2:3 hoặc 3:2."
                ),
                "Size": (
                    "Kích thước render thật theo Frame + Quality. App tự tính width/height để video "
                    "xuất ra đúng tỉ lệ và đúng chất lượng."
                ),
                "FPS": (
                    "Số khung hình mỗi giây của video. 30 FPS là mặc định mượt và phù hợp đa số video kể chuyện."
                ),
                "Codec": (
                    "auto sẽ tự phát hiện GPU encoder như h264_nvenc, h264_qsv hoặc h264_amf; "
                    "nếu không có sẽ dùng libx264 CPU. Chọn libx264 để ép chạy CPU."
                ),
                "Pattern": (
                    "Danh sách hiệu ứng camera dùng cho ảnh: pan_lr, pan_ud, zoom_in, zoom_out, combo. "
                    "Khi bật Random effects, mỗi ảnh sẽ chọn một hiệu ứng và tránh lặp ngay cảnh kế tiếp."
                ),
            },
        )
        self.video_effect_aspect_ratio.setToolTip(
            "Tỉ lệ khung hình đầu ra. Ảnh/video sẽ bị crop vừa khung để đúng tỉ lệ này."
        )
        self.video_effect_quality.setToolTip(
            "Preset chất lượng render thật: HD, FHD, 2K hoặc 4K. App tự đổi thành kích thước pixel phù hợp tỉ lệ."
        )
        self.video_effect_crf.setToolTip(
            "CRF càng thấp thì chất lượng càng cao và file càng nặng. 18 là mức chất lượng tốt."
        )
        self.video_effect_workers.setToolTip(
            "Số đoạn render song song. 2 là an toàn; máy khỏe có thể thử 3 hoặc 4, nhưng quá cao dễ nghẽn RAM/I/O."
        )
        self.video_effect_random_effects.setToolTip(
            "Bật chọn hiệu ứng ngẫu nhiên cho từng ảnh, ví dụ ảnh này pan, ảnh kia zoom, ảnh khác combo."
        )
        self.video_effect_bounce.setToolTip(
            "Bật chuyển động đi tới rồi quay ngược lại, như camera trượt sang rồi quay về hoặc zoom rồi lùi lại."
        )
        self.video_effect_merge.setToolTip(
            "Bật ghép toàn bộ video segment sau khi render. Video lẻ vẫn nằm trong thư mục segments."
        )
        video_effect_render_group = QGroupBox("Render")
        video_effect_render_group.setLayout(video_effect_render_form)

        video_effect_motion_form = QFormLayout()
        video_effect_motion_form.addRow(
            "Template",
            self.inline_controls(
                self.video_effect_motion_template,
                self.button("Save Template", self.save_video_effect_motion_template),
                self.button("Delete", self.delete_video_effect_motion_template),
            ),
        )
        video_effect_motion_form.addRow(
            "Zoom",
            self.paired_controls(self.video_effect_zoom_scale, "Face safe", self.video_effect_face_safe),
        )
        video_effect_motion_form.addRow(
            "Base crop",
            self.paired_controls(
                self.video_effect_base_crop, "Edge reach", self.video_effect_edge_reach
            ),
        )
        video_effect_motion_form.addRow(
            "Speed",
            self.paired_controls(self.video_effect_speed, "Pre silence", self.video_effect_pre_silence),
        )
        video_effect_motion_form.addRow("Min motion", self.video_effect_min_motion)
        video_effect_motion_form.addRow(
            "Combo radius",
            self.paired_controls(
                self.video_effect_combo_radius, "Offset X", self.video_effect_combo_offset_x
            ),
        )
        video_effect_motion_form.addRow("Combo offset Y", self.video_effect_combo_offset_y)
        self.set_form_tooltips(
            video_effect_motion_form,
            {
                "Template": (
                    "Nạp Basic Motion, Hard Motion hoặc template tự lưu. Save Template lưu toàn bộ "
                    "tham số motion hiện tại."
                ),
                "Zoom": (
                    "Mức zoom tối đa theo tỷ lệ trực tiếp: 0.02 = 2%, 0.10 = 10%. "
                    "Đặt 0 để tắt phần zoom động."
                ),
                "Base crop": (
                    "Phần crop nền dành cho chuyển động pan: 0.00 giữ tối đa ảnh, 0.02 crop thêm 2%. "
                    "Tăng giá trị này cho pan rộng hơn nhưng sẽ mất nhiều nội dung ở mép ảnh."
                ),
                "Speed": (
                    "Tốc độ chuyển động camera. Số càng lớn thì hiệu ứng chạy càng nhanh, bounce cũng rõ hơn."
                ),
                "Min motion": (
                    "Mức chuyển động tối thiểu để tránh đoạn video nhìn như đứng im hoàn toàn."
                ),
                "Combo radius": (
                    "Độ rộng quỹ đạo combo dạng tròn/elip. Tăng lên thì camera đảo quanh mạnh hơn."
                ),
                "Combo offset Y": (
                    "Dịch tâm quỹ đạo combo theo chiều dọc. Âm thường đẩy tâm lên trên để giữ nhân vật trong khung."
                ),
            },
        )
        self.video_effect_face_safe.setToolTip(
            "Mức ưu tiên giữ phần đầu nhân vật trong khung hình. Tăng lên 2.0 nếu ảnh vẫn bị cắt đầu."
        )
        self.video_effect_base_crop.setToolTip(
            "Crop nền trước motion. Khuyên dùng 0.00-0.03; giá trị cũ tương đương khoảng 0.35."
        )
        self.video_effect_edge_reach.setToolTip(
            "Tỷ lệ vùng pan được sử dụng: 0.66 là chuyển động vừa; 1.00 đi tới sát biên ảnh khả dụng."
        )
        self.video_effect_pre_silence.setToolTip(
            "Thêm khoảng im lặng trước mỗi audio, ví dụ 0.30 giây, để các đoạn có nhịp nghỉ tự nhiên."
        )
        self.video_effect_combo_offset_x.setToolTip(
            "Dịch tâm quỹ đạo combo theo chiều ngang. Dùng để lệch nhẹ chuyển động sang trái/phải."
        )
        video_effect_motion_group = QGroupBox("Motion")
        video_effect_motion_group.setLayout(video_effect_motion_form)

        video_effect_retro_form = QFormLayout()
        video_effect_retro_form.addRow("Preset", self.video_effect_retro_preset)
        self.video_effect_retro_sections = []

        def retro_effect_section(
            checkbox: QCheckBox, rows: list[tuple[str, QWidget]], tooltip: str
        ) -> QWidget:
            wrapper = QWidget()
            layout = QVBoxLayout(wrapper)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(4)
            checkbox.setToolTip(tooltip)
            params = QWidget()
            params_layout = QFormLayout(params)
            params_layout.setContentsMargins(18, 0, 0, 6)
            params_layout.setSpacing(6)
            for label, widget in rows:
                params_layout.addRow(label, widget)
            self.align_left_form(params_layout)
            layout.addWidget(checkbox)
            layout.addWidget(params)
            checkbox.toggled.connect(params.setVisible)
            params.setVisible(checkbox.isChecked())
            self.video_effect_retro_sections.append(params)
            return wrapper

        video_effect_retro_form.addRow(
            retro_effect_section(
                self.video_effect_retro_scratches_enabled,
                [("Amount", self.video_effect_retro_scratch)],
                "Vết trầy đen/trắng xuất hiện ngẫu nhiên trên nhiều vị trí của video.",
            )
        )
        video_effect_retro_form.addRow(
            retro_effect_section(
                self.video_effect_retro_dust_enabled,
                [("Amount", self.video_effect_retro_dust)],
                "Chấm bụi đen/trắng chớp ngẫu nhiên trên khung hình như film cũ.",
            )
        )
        video_effect_retro_form.addRow(
            retro_effect_section(
                self.video_effect_retro_grain_enabled,
                [("Amount", self.video_effect_retro_grain)],
                "Hạt nhiễu mịn phủ lên ảnh để tạo cảm giác film nhựa.",
            )
        )
        video_effect_retro_form.addRow(
            retro_effect_section(
                self.video_effect_retro_flicker_enabled,
                [("Strength", self.video_effect_retro_flicker)],
                "Nhấp nháy sáng tối theo từng frame như máy chiếu film cũ.",
            )
        )
        video_effect_retro_form.addRow(
            retro_effect_section(
                self.video_effect_retro_vignette_enabled,
                [("Strength", self.video_effect_retro_vignette)],
                "Làm tối viền khung hình để tạo cảm giác ống kính/film cũ.",
            )
        )
        video_effect_retro_form.addRow(
            retro_effect_section(
                self.video_effect_retro_color_fade_enabled,
                [("Strength", self.video_effect_retro_color_fade)],
                "Giảm màu, giảm độ tươi và làm ảnh hơi ngả vàng kiểu film đã bạc màu.",
            )
        )
        video_effect_retro_form.addRow(
            retro_effect_section(
                self.video_effect_retro_scan_lines_enabled,
                [("Opacity", self.video_effect_retro_scan_lines)],
                "Thêm các vạch ngang nhẹ kiểu băng/video cũ.",
            )
        )
        self.set_form_tooltips(
            video_effect_retro_form,
            {
                "Preset": (
                    "Chọn nhanh bộ hiệu ứng film nhựa cũ. Off tắt tất cả; Custom dùng lựa chọn bạn tự chỉnh."
                ),
            },
        )
        self.video_effect_retro_scratch.setToolTip("Số lượng vết trầy xuất hiện mỗi frame.")
        self.video_effect_retro_dust.setToolTip("Số lượng chấm bụi xuất hiện mỗi frame.")
        self.video_effect_retro_grain.setToolTip("Độ mạnh của hạt nhiễu film.")
        self.video_effect_retro_flicker.setToolTip("Biên độ nhấp nháy sáng tối.")
        self.video_effect_retro_vignette.setToolTip("Độ tối viền khung hình.")
        self.video_effect_retro_color_fade.setToolTip("Mức bạc màu và giảm độ tươi.")
        self.video_effect_retro_scan_lines.setToolTip("Độ rõ của vạch ngang scan line.")
        video_effect_retro_group = QGroupBox("Retro Film")
        video_effect_retro_group.setLayout(video_effect_retro_form)
        for form in (video_effect_render_form, video_effect_motion_form, video_effect_retro_form):
            self.align_left_form(form)
        for group in (
            video_effect_input_group,
            video_effect_render_group,
            video_effect_motion_group,
            video_effect_retro_group,
        ):
            self.make_group_collapsible(group)

        video_effect_left_panel = QWidget()
        video_effect_left_panel.setMinimumWidth(560)
        video_effect_left_panel.setMaximumWidth(580)
        video_effect_left_layout = QVBoxLayout(video_effect_left_panel)
        video_effect_left_layout.addWidget(video_effect_input_group)
        video_effect_left_layout.addWidget(video_effect_render_group)
        video_effect_left_layout.addWidget(video_effect_motion_group)
        video_effect_left_layout.addWidget(video_effect_retro_group)
        video_effect_settings_actions = QHBoxLayout()
        video_effect_settings_actions.addWidget(self.button("Save Settings", self.save_video_effect_settings), 1)
        video_effect_settings_actions.addWidget(self.button("Load defaults", self.load_video_effect_defaults), 1)
        video_effect_left_layout.addLayout(video_effect_settings_actions)
        video_effect_left_layout.addStretch()
        video_effect_left_scroll = QScrollArea()
        video_effect_left_scroll.setWidgetResizable(True)
        video_effect_left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        video_effect_left_scroll.setMinimumWidth(580)
        video_effect_left_scroll.setMaximumWidth(600)
        video_effect_left_scroll.setWidget(video_effect_left_panel)

        video_effect_right_panel = QWidget()
        video_effect_right_layout = QVBoxLayout(video_effect_right_panel)
        video_effect_right_layout.addWidget(QLabel("Realtime processing log"))
        video_effect_right_layout.addWidget(self.video_effect_log)
        video_effect_right_layout.addWidget(self.video_effect_progress)
        video_effect_right_layout.addWidget(self.video_effect_status)

        video_effect_splitter = QSplitter(Qt.Orientation.Horizontal)
        video_effect_splitter.addWidget(video_effect_left_scroll)
        video_effect_splitter.addWidget(video_effect_right_panel)
        video_effect_splitter.setSizes([560, 720])
        video_effect_tab = QWidget()
        video_effect_layout = QVBoxLayout(video_effect_tab)
        video_effect_layout.addWidget(video_effect_splitter)
        self.video_effect_render_button = self.button("Render video effects", self.start_video_effect)
        self.video_effect_stop_button = self.button("Stop Video Effect", self.stop_current_render)
        self.video_effect_open_output_button = self.button(
            "Open output folder", self.open_video_effect_output_folder
        )
        self.video_effect_stop_button.setEnabled(False)
        video_effect_action_row = QHBoxLayout()
        video_effect_action_row.addWidget(self.video_effect_render_button)
        video_effect_action_row.addWidget(self.video_effect_stop_button)
        video_effect_action_row.addWidget(self.video_effect_open_output_button)
        video_effect_layout.addLayout(video_effect_action_row)

        # Keep the MOSS implementation and saved settings available for a future
        # re-enable, but hide Voice Clone v2 because the workflow is not stable
        # enough for normal use yet.
        self.moss_tab_enabled = False
        moss_tab = self.build_moss_tab()
        self.chatterbox_v3_tab = ChatterboxV3Tab(
            self.store,
            lambda: str(self.voice_profile.currentData() or self.profile.currentData() or ""),
            config_dir(),
            self,
        )
        caption_tab = self.build_caption_tab()
        watermark_tab = self.build_watermark_tab()
        tools_tab = self.build_tools_tab()
        automation_tab = self.build_automation_tab()
        tabs = QTabWidget()
        tabs.addTab(clone_tab, "Voice List")
        tabs.addTab(voice_over_tab, "Voice Clone")
        moss_tab_index = tabs.addTab(moss_tab, "Voice Clone v2")
        tabs.setTabVisible(moss_tab_index, self.moss_tab_enabled)
        tabs.addTab(self.chatterbox_v3_tab, "Voice Clone v3")
        tabs.addTab(video_effect_tab, "Video Effect")
        tabs.addTab(caption_tab, "Caption")
        tabs.addTab(watermark_tab, "Watermark")
        tabs.addTab(automation_tab, "Automation")
        tabs.addTab(tools_tab, "Tools")
        tabs.addTab(settings_tab, "Environment")
        self.main_tabs = tabs
        self.main_tab_bar = tabs.tabBar()
        self.main_tabs.installEventFilter(self)
        self.main_tab_bar.installEventFilter(self)
        tabs.setCornerWidget(self.build_window_brand_widget(), Qt.Corner.TopRightCorner)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(tabs)
        container = QWidget()
        container.setObjectName("appRoot")
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.profile.currentIndexChanged.connect(
            lambda _index: self.load_profile(str(self.profile.currentData() or ""))
        )
        self.voice_profile.currentIndexChanged.connect(
            lambda _index: self.load_profile(str(self.voice_profile.currentData() or ""))
        )
        self.voice_profile.currentIndexChanged.connect(lambda _index: self.update_default_voice_profile_button())
        self.output_format.currentTextChanged.connect(self.refresh_segment_table)
        self.style_mode.currentIndexChanged.connect(self.refresh_segment_table)
        self.speaking_style.activated.connect(self.refresh_segment_table)
        self.speaking_style.lineEdit().editingFinished.connect(self.refresh_segment_table)
        self.use_speaking_style.toggled.connect(self.update_style_controls)
        self.zonos2_input_file.textChanged.connect(self.refresh_zonos2_range)
        self.zonos2_input_file.textChanged.connect(self.refresh_zonos2_segment_table)
        self.zonos2_output_format.currentTextChanged.connect(self.refresh_zonos2_segment_table)
        self.zonos2_output_dir.editingFinished.connect(self.refresh_zonos2_segment_table)
        self.video_effect_aspect_ratio.currentTextChanged.connect(self.update_video_effect_dimensions)
        self.video_effect_quality.currentTextChanged.connect(self.update_video_effect_dimensions)
        self.video_effect_motion_template.currentTextChanged.connect(
            self.apply_video_effect_motion_template
        )
        for widget in (
            self.video_effect_zoom_scale,
            self.video_effect_base_crop,
            self.video_effect_edge_reach,
            self.video_effect_face_safe,
            self.video_effect_speed,
            self.video_effect_min_motion,
            self.video_effect_combo_radius,
            self.video_effect_combo_offset_x,
            self.video_effect_combo_offset_y,
        ):
            widget.valueChanged.connect(self.mark_video_effect_motion_custom)
        self.video_effect_pattern.textChanged.connect(self.mark_video_effect_motion_custom)
        self.video_effect_random_effects.toggled.connect(self.mark_video_effect_motion_custom)
        self.video_effect_bounce.toggled.connect(self.mark_video_effect_motion_custom)
        self.video_effect_retro_preset.currentTextChanged.connect(self.apply_video_effect_retro_preset)
        for widget in (
            self.video_effect_retro_scratch,
            self.video_effect_retro_dust,
            self.video_effect_retro_grain,
            self.video_effect_retro_flicker,
            self.video_effect_retro_vignette,
            self.video_effect_retro_color_fade,
            self.video_effect_retro_scan_lines,
        ):
            widget.valueChanged.connect(self.mark_video_effect_retro_custom)
        for checkbox in (
            self.video_effect_retro_scratches_enabled,
            self.video_effect_retro_dust_enabled,
            self.video_effect_retro_grain_enabled,
            self.video_effect_retro_flicker_enabled,
            self.video_effect_retro_vignette_enabled,
            self.video_effect_retro_color_fade_enabled,
            self.video_effect_retro_scan_lines_enabled,
        ):
            checkbox.toggled.connect(self.mark_video_effect_retro_custom)
        self.connect_caption_signals()
        self.restore_saved_caption_configuration()
        self.update_style_controls()
        self.update_video_effect_dimensions()
        self.apply_video_effect_motion_template(self.video_effect_motion_template.currentText())
        self.apply_video_effect_retro_preset()
        self.update_caption_mode()
        self.update_caption_preview()
        self.connect_watermark_signals()
        self.update_watermark_preview()
        self.refresh_profiles()
        self.add_batch_row(output_path=self.settings.get("output_dir", ""), checked=True)
        self.apply_ui_language()
        if os.environ.get("QT_QPA_PLATFORM", "").lower() != "offscreen":
            self.chatterbox_v3_tab.start_preload()

    def build_moss_tab(self) -> QWidget:
        self.active_moss_output_dir: Path | None = None
        self.moss_batch_rows: list[dict] = []
        self.moss_current_row: dict | None = None
        self.moss_batch_queue: list[dict] = []
        self.moss_batch_outputs: list[str] = []
        self.moss_batch_index = 0
        self.moss_batch_running = False
        self.moss_job_succeeded = False
        self.moss_pipeline_phase = "idle"
        self.moss_pipeline_check_positions: list[int] = []
        self.moss_pipeline_retry_queue: list[int] = []
        self.moss_pipeline_retry_counts: dict[int, int] = {}
        self.moss_pipeline_current_retry: int | None = None
        self.moss_pipeline_unresolved: list[int] = []
        self.moss_pipeline_cancelled = False
        self.moss_qa_thread: QThread | None = None
        self.moss_qa_worker: MossAudioCheckWorker | None = None
        self.moss_qa_round_phase = "idle"
        self.moss_qa_round_finished = False
        self.moss_qa_requested_positions: list[int] = []
        self.moss_pipeline_pending_recheck: list[int] = []
        self.moss_retry_start_pending = False
        self.moss_review_items: dict[int, QListWidgetItem] = {}
        self.moss_review_reasons: dict[int, str] = {}
        self.moss_profile = QComboBox()
        self.moss_input_file = QLineEdit(self.settings.get("moss_input_file", ""))
        self.moss_output_dir = QLineEdit(self.settings["moss_output_dir"])
        self.moss_segment_text_input = QPlainTextEdit()
        self.moss_segment_text_input.setPlaceholderText(
            "Dán một hoặc nhiều đoạn. Ngăn cách các đoạn bằng một dòng trống. "
            "Có thể chèn khoảng nghỉ: [pause 1.5s]"
        )
        self.moss_segment_text_input.setMaximumHeight(110)
        self.moss_model_name = QComboBox()
        self.moss_model_name.setEditable(True)
        self.moss_model_name.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.moss_model_name.setMinimumContentsLength(34)
        for label, repo_id, _description in MOSS_CHECKPOINT_OPTIONS:
            self.moss_model_name.addItem(label, repo_id)
        self.set_moss_checkpoint(self.settings["moss_model_name"])
        self.moss_load_model_button = self.button(
            "Download / Load", self.load_selected_moss_checkpoint
        )
        self.moss_device = QComboBox()
        self.moss_device.addItem("CUDA GPU", "cuda")
        self.moss_device.addItem("CPU (rất chậm, cần nhiều RAM)", "cpu")
        self.moss_device.setCurrentIndex(max(0, self.moss_device.findData(self.settings["moss_compute_device"])))
        self.moss_dtype = QComboBox()
        self.moss_dtype.addItem("BFloat16 (khuyên dùng)", "bfloat16")
        self.moss_dtype.addItem("Float16", "float16")
        self.moss_dtype.setCurrentIndex(max(0, self.moss_dtype.findData(self.settings["moss_dtype"])))
        self.moss_attention = QComboBox()
        self.moss_attention.addItem("Auto", "auto")
        self.moss_attention.addItem("PyTorch SDPA", "sdpa")
        self.moss_attention.addItem("FlashAttention 2", "flash_attention_2")
        self.moss_attention.addItem("Eager (CPU)", "eager")
        self.moss_attention.setCurrentIndex(max(0, self.moss_attention.findData(self.settings["moss_attention"])))
        self.moss_language = QComboBox()
        for code, name in MossTTSWorker.LANGUAGE_NAMES.items():
            self.moss_language.addItem(f"{name} ({code})", code)
        self.moss_language.setCurrentIndex(max(0, self.moss_language.findData(self.settings["moss_language"])))
        self.moss_max_new_tokens = QSpinBox()
        self.moss_max_new_tokens.setRange(256, 16384)
        self.moss_max_new_tokens.setSingleStep(256)
        self.moss_max_new_tokens.setValue(setting_int(self.settings, "moss_max_new_tokens"))
        self.moss_auto_duration = QCheckBox(
            "Auto duration guard (recommended — prevents runaway audio)"
        )
        self.moss_auto_duration.setChecked(setting_bool(self.settings, "moss_auto_duration"))
        self.moss_auto_qa_retry = QCheckBox(
            "Auto ASR check + rerender failed segments"
        )
        self.moss_auto_qa_retry.setChecked(setting_bool(self.settings, "moss_auto_qa_retry"))
        self.moss_auto_qa_max_retries = QSpinBox()
        self.moss_auto_qa_max_retries.setRange(1, 10)
        self.moss_auto_qa_max_retries.setValue(
            setting_int(self.settings, "moss_auto_qa_max_retries")
        )
        self.moss_asr_workers = QSpinBox()
        self.moss_asr_workers.setRange(1, 8)
        self.moss_asr_workers.setValue(setting_int(self.settings, "moss_asr_workers"))
        self.moss_preview_count = QSpinBox()
        self.moss_preview_count.setRange(1, 2)
        self.moss_preview_count.setValue(setting_int(self.settings, "moss_preview_count"))
        self.moss_cooldown = QSpinBox()
        self.moss_cooldown.setRange(0, 60)
        self.moss_cooldown.setValue(setting_int(self.settings, "moss_cooldown_seconds"))
        self.moss_output_format = QComboBox()
        self.moss_output_format.addItems(["wav", "mp3"])
        self.moss_output_format.setCurrentText(self.settings["moss_output_format"])
        self.moss_merge_pause = QDoubleSpinBox()
        self.moss_merge_pause.setRange(0, 10)
        self.moss_merge_pause.setDecimals(2)
        self.moss_merge_pause.setValue(float(self.settings["moss_merge_pause"]))
        self.moss_merge_pause.setSuffix(" sec")
        self.moss_normalize = QCheckBox("Normalize completed batch after all segments render")
        self.moss_normalize.setChecked(setting_bool(self.settings, "moss_normalize_audio"))
        self.moss_overwrite = QCheckBox("Overwrite existing files in selected range")
        self.moss_range_from = QSpinBox()
        self.moss_range_from.setRange(1, 1)
        self.moss_range_to = QSpinBox()
        self.moss_range_to.setRange(1, 1)
        self.moss_progress = QProgressBar()
        self.moss_status = QLabel("Ready")
        self.moss_timing_label = QLabel("Elapsed 00:00:00 · ETA waiting for first segment")
        self.moss_timing_label.setWordWrap(True)
        self.moss_timing_started_at: float | None = None
        self.moss_timing_total = 0
        self.moss_timing_completed = 0
        self.moss_timing_samples: list[float] = []
        self.moss_timing_timer = QTimer(self)
        self.moss_timing_timer.setInterval(1000)
        self.moss_timing_timer.timeout.connect(self.update_moss_timing_clock)
        self.moss_log = TranslatedLogEdit()
        self.moss_log.setReadOnly(True)
        self.moss_log.setMaximumBlockCount(500)
        self.moss_log.setMaximumHeight(120)
        self.moss_review_list = QListWidget()
        self.moss_review_list.setMaximumHeight(125)
        self.moss_review_list.setToolTip(
            "QA issues and automatically repaired segments. Double-click to select and play."
        )
        self.moss_review_list.itemDoubleClicked.connect(self.open_moss_review_item)

        voice_form = QFormLayout()
        voice_form.addRow("Voice profile", self.moss_profile)
        voice_group = QGroupBox("Voice and Input")
        voice_group.setLayout(voice_form)

        self.moss_batch_container = QWidget()
        self.moss_batch_layout = QVBoxLayout(self.moss_batch_container)
        self.moss_batch_layout.setContentsMargins(4, 4, 4, 4)
        self.moss_batch_layout.setSpacing(6)
        self.moss_batch_scroll = QScrollArea()
        self.moss_batch_scroll.setWidgetResizable(True)
        self.moss_batch_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.moss_batch_scroll.setWidget(self.moss_batch_container)
        self.moss_add_row_button = self.button("+ Add Task Row", self.add_moss_batch_row_clicked)
        moss_batch_group_layout = QVBoxLayout()
        moss_batch_group_layout.addWidget(self.moss_batch_scroll)
        moss_batch_group_layout.addWidget(self.moss_add_row_button)
        moss_batch_group = QGroupBox("Batch Processing Queue")
        moss_batch_group.setLayout(moss_batch_group_layout)
        initial_moss_row = self.add_moss_batch_row(
            checked=True,
            input_edit=self.moss_input_file,
            output_edit=self.moss_output_dir,
        )
        saved_moss_session_text = self.settings.get("moss_last_session_dir", "").strip()
        saved_moss_session = Path(saved_moss_session_text) if saved_moss_session_text else None
        if saved_moss_session is not None and saved_moss_session.is_dir():
            initial_moss_row["active_output_dir"] = saved_moss_session
            self.active_moss_output_dir = saved_moss_session

        generation_form = QFormLayout()
        generation_form.addRow(
            "Checkpoint", self.inline_controls(self.moss_model_name, self.moss_load_model_button)
        )
        generation_form.addRow("Language", self.moss_language)
        generation_form.addRow("Compute", self.paired_controls(self.moss_device, "Dtype", self.moss_dtype))
        generation_form.addRow("Attention", self.moss_attention)
        generation_form.addRow("Max new tokens", self.moss_max_new_tokens)
        generation_form.addRow("", self.moss_auto_duration)
        generation_form.addRow("", self.moss_auto_qa_retry)
        generation_form.addRow("Max QA retries", self.moss_auto_qa_max_retries)
        generation_form.addRow("Parallel ASR workers", self.moss_asr_workers)
        self.moss_checkpoint_note = QLabel()
        self.moss_checkpoint_note.setWordWrap(True)
        self.moss_model_name.currentIndexChanged.connect(self.update_moss_checkpoint_note)
        if self.moss_model_name.lineEdit() is not None:
            self.moss_model_name.lineEdit().textChanged.connect(self.update_moss_checkpoint_note)
        self.update_moss_checkpoint_note()
        generation_form.addRow("", self.moss_checkpoint_note)
        generation_group = QGroupBox("MOSS-TTS Configuration")
        generation_group.setLayout(generation_form)

        output_form = QFormLayout()
        output_form.addRow("Format", self.paired_controls(self.moss_output_format, "Merge pause", self.moss_merge_pause))
        output_form.addRow("Preview segments", self.paired_controls(self.moss_preview_count, "Cooldown", self.moss_cooldown))
        output_form.addRow("", self.moss_normalize)
        range_widget = QWidget()
        range_layout = QHBoxLayout(range_widget)
        range_layout.setContentsMargins(0, 0, 0, 0)
        range_layout.addWidget(QLabel("From"))
        range_layout.addWidget(self.moss_range_from)
        range_layout.addWidget(QLabel("To"))
        range_layout.addWidget(self.moss_range_to)
        output_form.addRow("Render range", range_widget)
        output_form.addRow("", self.moss_overwrite)
        output_group = QGroupBox("Output and Audio")
        output_group.setLayout(output_form)
        for form in (voice_form, generation_form, output_form):
            self.align_left_form(form)

        left_panel = QWidget()
        left_panel.setMinimumWidth(560)
        left_panel.setMaximumWidth(580)
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(voice_group)
        left_layout.addWidget(moss_batch_group)
        left_layout.addWidget(generation_group)
        left_layout.addWidget(output_group)
        settings_actions = QHBoxLayout()
        settings_actions.addWidget(self.button("Save Settings", self.save_moss_settings))
        settings_actions.addWidget(self.button("Load defaults", self.load_moss_defaults))
        left_layout.addLayout(settings_actions)
        left_layout.addStretch()

        self.moss_segment_table = QTableWidget(0, 5)
        self.moss_segment_table.setHorizontalHeaderLabels(["#", "Time", "Text", "Status", "Actions"])
        self.moss_segment_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.moss_segment_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.moss_segment_table.verticalHeader().setVisible(False)
        moss_header = self.moss_segment_table.horizontalHeader()
        for column in (0, 1, 3, 4):
            moss_header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        moss_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.addWidget(QLabel("Voice-over segments"))
        right_layout.addWidget(self.moss_segment_text_input)
        self.moss_add_segments_button = self.button("Add text segments", self.add_moss_text_segments)
        right_layout.addWidget(self.moss_add_segments_button)
        right_layout.addWidget(self.moss_segment_table)
        right_layout.addWidget(self.moss_progress)
        right_layout.addWidget(self.moss_status)
        right_layout.addWidget(self.moss_timing_label)
        right_layout.addWidget(QLabel("ASR review / automatic repair queue"))
        right_layout.addWidget(self.moss_review_list)
        right_layout.addWidget(self.moss_log)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([560, 720])

        self.moss_preview_button = self.button("Render preview", self.render_moss_preview)
        self.moss_render_button = self.button("Render all segments", self.start_moss)
        self.moss_range_button = self.button("Render selected range", self.render_moss_range)
        self.moss_stop_button = self.button("Stop current render", self.stop_current_render)
        self.moss_merge_button = self.button("Merge numbered audio files", self.merge_moss_audio)
        self.moss_check_audio_button = self.button(
            "Check all audio (ASR)", self.start_moss_audio_check
        )
        self.moss_select_session_button = self.button(
            "Select existing session", self.select_existing_moss_session
        )
        self.moss_open_output_button = self.button("Open output folder", self.open_moss_output_folder)
        self.moss_stop_button.setEnabled(False)
        actions = QHBoxLayout()
        for button in (self.moss_preview_button, self.moss_render_button, self.moss_range_button,
                       self.moss_stop_button, self.moss_merge_button,
                       self.moss_check_audio_button, self.moss_select_session_button,
                       self.moss_open_output_button):
            actions.addWidget(button)
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(splitter)
        layout.addLayout(actions)
        self.moss_output_format.currentTextChanged.connect(self.refresh_moss_segments)
        return tab

    @property
    def input_file(self) -> QLineEdit:
        row = self.current_live_batch_row()
        if row:
            return row["input_edit"]
        if not hasattr(self, "_fallback_input_file"):
            self._fallback_input_file = QLineEdit()
        return self._fallback_input_file

    @property
    def output_dir(self) -> QLineEdit:
        row = self.current_live_batch_row()
        if row:
            return row["output_edit"]
        if not hasattr(self, "_fallback_output_dir"):
            self._fallback_output_dir = QLineEdit()
        return self._fallback_output_dir

    def current_live_batch_row(self) -> dict | None:
        row = getattr(self, "current_view_row", None)
        if not row:
            return None
        try:
            row["widget"].objectName()
            row["input_edit"].objectName()
            row["output_edit"].objectName()
        except RuntimeError:
            self.current_view_row = self.batch_rows[0] if self.batch_rows else None
            return self.current_live_batch_row()
        return row

    def get_active_input_path(self) -> str:
        row = self.current_live_batch_row()
        if row:
            return row["input_edit"].text().strip()
        return ""

    def get_active_output_path(self) -> str:
        row = self.current_live_batch_row()
        if row:
            return row["output_edit"].text().strip()
        return ""

    def add_batch_row(self, input_path="", output_path="", checked=False) -> dict:
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)
        
        view_radio = QRadioButton()
        view_radio.setToolTip("Select to view this file's segments in the table")
        view_radio.setFixedWidth(20)
        
        input_edit = QLineEdit(input_path)
        input_edit.setPlaceholderText("SRT/TXT input file")
        input_edit.setToolTip("Path to SRT or TXT script file")
        
        output_edit = QLineEdit(output_path)
        output_edit.setPlaceholderText("Output folder")
        output_edit.setToolTip("Folder where voiceover audio segments will be saved")
        
        browse_input = QPushButton("Browse")
        browse_input.setFixedWidth(65)
        browse_output = QPushButton("Browse")
        browse_output.setFixedWidth(65)
        
        remove_btn = QPushButton("✕")
        remove_btn.setFixedWidth(28)
        remove_btn.setStyleSheet("color: #ff5555; font-weight: bold; background: #2d1818; border: 1px solid #552222;")
        
        row_layout.addWidget(view_radio)
        row_layout.addWidget(input_edit, 3)
        row_layout.addWidget(browse_input)
        row_layout.addWidget(output_edit, 3)
        row_layout.addWidget(browse_output)
        row_layout.addWidget(remove_btn)
        
        index = len(self.batch_rows)
        self.batch_layout.insertWidget(index, row_widget)
        
        row_dict = {
            "widget": row_widget,
            "view_radio": view_radio,
            "input_edit": input_edit,
            "output_edit": output_edit,
            "browse_input": browse_input,
            "browse_output": browse_output,
            "remove_btn": remove_btn
        }
        self.batch_rows.append(row_dict)
        
        browse_input.clicked.connect(lambda: self.pick_row_input(input_edit, output_edit))
        browse_output.clicked.connect(lambda: self.pick_row_output(output_edit))
        remove_btn.clicked.connect(lambda: self.remove_batch_row(row_dict))
        
        view_radio.toggled.connect(lambda checked_state: self.on_row_radio_toggled(row_dict, checked_state))
        input_edit.textChanged.connect(self.on_row_text_changed)
        output_edit.textChanged.connect(self.on_row_text_changed)
        
        if checked:
            view_radio.setChecked(True)
            self.current_view_row = row_dict
            
        self.update_batch_scroll_height()
        return row_dict

    def add_batch_row_clicked(self) -> None:
        row_dict = self.add_batch_row()
        if len(self.batch_rows) == 1:
            row_dict["view_radio"].setChecked(True)

    def remove_batch_row(self, row_dict: dict) -> None:
        if len(self.batch_rows) <= 1:
            QMessageBox.information(self, "Batch Queue", "You must have at least one task row.")
            return
            
        was_checked = row_dict["view_radio"].isChecked()
        
        self.batch_rows.remove(row_dict)
        self.batch_layout.removeWidget(row_dict["widget"])
        row_dict["widget"].deleteLater()
        
        if was_checked and self.batch_rows:
            self.batch_rows[0]["view_radio"].setChecked(True)
            self.current_view_row = self.batch_rows[0]
            self.refresh_segment_table()
        elif not self.batch_rows:
            self.current_view_row = None
            self.refresh_segment_table()
            
        self.update_batch_scroll_height()

    def update_batch_scroll_height(self) -> None:
        row_count = len(self.batch_rows)
        row_height = 32
        spacing = 6
        margins = 8
        if row_count <= 3:
            needed_height = row_count * row_height + max(0, row_count - 1) * spacing + margins
            self.batch_scroll.setFixedHeight(needed_height)
        else:
            cap_height = int(3.5 * row_height + 3 * spacing + margins)
            self.batch_scroll.setFixedHeight(cap_height)

    def pick_row_input(self, input_edit: QLineEdit, output_edit: QLineEdit) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Script", "", "Script (*.srt *.txt)")
        if path:
            self.segment_style_overrides.clear()
            input_edit.setText(path)
            if not output_edit.text():
                output_edit.setText(str(Path(path).with_name(Path(path).stem + "_voiceover")))
            self.refresh_segment_table()

    def pick_row_output(self, output_edit: QLineEdit) -> None:
        path = QFileDialog.getExistingDirectory(self, "Output folder")
        if path:
            output_edit.setText(path)
            self.refresh_segment_table()

    def on_row_radio_toggled(self, row_dict: dict, checked: bool) -> None:
        if checked:
            self.current_view_row = row_dict
            self.refresh_segment_table()

    def on_row_text_changed(self) -> None:
        sender = self.sender()
        if hasattr(self, "current_view_row") and self.current_view_row:
            if sender in (self.current_view_row["input_edit"], self.current_view_row["output_edit"]):
                self.refresh_segment_table()

    def button(self, text: str, callback) -> QPushButton:
        button = QPushButton(text)
        button.setProperty("_i18n_text", text)
        if getattr(self, "ui_language", "en") == "vi":
            button.setText(self.translated_ui_text(text))
        button.clicked.connect(callback)
        return button

    def start_omnivoice_preload(self) -> None:
        if self.preload_thread and self.preload_thread.isRunning():
            return
        model_name = self.model_name.text().strip() or DEFAULT_MODEL
        device_mode = str(self.compute_device.currentData() or "cuda")
        if device_mode == "cpu":
            self.append_log("OmniVoice preload skipped in CPU mode; render will load it on demand.")
            return
        self.preload_worker = OmniVoicePreloadWorker(model_name, device_mode)
        self.preload_thread = QThread()
        self.preload_worker.moveToThread(self.preload_thread)
        self.preload_thread.started.connect(self.preload_worker.run)
        self.preload_worker.completed.connect(self.on_omnivoice_preloaded)
        self.preload_worker.failed.connect(self.on_omnivoice_preload_failed)
        self.preload_worker.completed.connect(self.preload_thread.quit)
        self.preload_worker.failed.connect(self.preload_thread.quit)
        self.preload_thread.finished.connect(self.on_omnivoice_preload_finished)
        self.append_log(f"Preloading OmniVoice checkpoint '{model_name}' in the background...")
        self.preload_thread.start()

    def on_omnivoice_preloaded(self, message: str) -> None:
        self.append_log(message)
        if not (self.thread and self.thread.isRunning()):
            self.status.setText(message)

    def on_omnivoice_preload_failed(self, details: str) -> None:
        self.append_log("OmniVoice background preload failed; render will retry normally.\n" + details)

    def on_omnivoice_preload_finished(self) -> None:
        self.preload_worker = None
        self.preload_thread = None

    def set_moss_checkpoint(self, model_name: str) -> None:
        normalized = model_name.strip().replace("\\", "/")
        for index in range(self.moss_model_name.count()):
            if str(self.moss_model_name.itemData(index)) == normalized:
                self.moss_model_name.setCurrentIndex(index)
                return
        self.moss_model_name.setEditText(model_name.strip() or DEFAULT_MOSS_MODEL)

    def selected_moss_checkpoint(self) -> str:
        index = self.moss_model_name.currentIndex()
        if index >= 0 and self.moss_model_name.currentText() == self.moss_model_name.itemText(index):
            repo_id = self.moss_model_name.itemData(index)
            if repo_id:
                return str(repo_id)
        return self.moss_model_name.currentText().strip() or DEFAULT_MOSS_MODEL

    def update_moss_checkpoint_note(self, *_args) -> None:
        if not hasattr(self, "moss_checkpoint_note"):
            return
        selected = self.selected_moss_checkpoint()
        for _label, repo_id, description in MOSS_CHECKPOINT_OPTIONS:
            if selected == repo_id:
                pause_note = (
                    " Supports [pause X.Ys]."
                    if repo_id.endswith("-v1.5") else
                    " This version does not have v1.5 language tags or explicit pause control."
                )
                self.moss_checkpoint_note.setText(
                    f"{description}{pause_note} Downloaded files remain in the Hugging Face cache."
                )
                return
        self.moss_checkpoint_note.setText(
            "Custom checkpoint or local folder. Compatibility is not guaranteed; "
            "Download / Load will validate it before rendering."
        )

    def load_selected_moss_checkpoint(self) -> None:
        if self.thread and self.thread.isRunning():
            QMessageBox.warning(self, "MOSS-TTS", "Wait for the current render to finish first.")
            return
        if self.preload_thread and self.preload_thread.isRunning():
            QMessageBox.information(self, "MOSS-TTS", "A model is already loading.")
            return
        self.persist_settings("voice_clone_v2")
        self.start_moss_preload()

    def start_moss_preload(self) -> None:
        if self.preload_thread and self.preload_thread.isRunning():
            return
        model_name = self.selected_moss_checkpoint()
        device_mode = str(self.moss_device.currentData() or "cuda")
        dtype_name = str(self.moss_dtype.currentData() or "bfloat16")
        attention = str(self.moss_attention.currentData() or "auto")
        self.active_task_ui = "moss"
        self.preload_worker = MossPreloadWorker(
            model_name, device_mode, dtype_name, attention
        )
        self.preload_thread = QThread()
        self.preload_worker.moveToThread(self.preload_thread)
        self.preload_thread.started.connect(self.preload_worker.run)
        self.preload_worker.completed.connect(self.on_moss_preloaded)
        self.preload_worker.failed.connect(self.on_moss_preload_failed)
        self.preload_worker.completed.connect(self.preload_thread.quit)
        self.preload_worker.failed.connect(self.preload_thread.quit)
        self.preload_thread.finished.connect(self.on_moss_preload_finished)
        self.set_busy(True, "Preloading MOSS-TTS on startup...")
        self.moss_timing_label.setText(
            f"Startup preload · {device_mode.upper()} · {dtype_name} · {attention}"
        )
        self.append_log(f"Preloading MOSS-TTS checkpoint '{model_name}' in the background...")
        self.preload_thread.start()

    def on_moss_preloaded(self, message: str) -> None:
        self.moss_status.setText(message)
        self.moss_timing_label.setText("Model preloaded and ready for immediate rendering")
        self.append_log(message)

    def on_moss_preload_failed(self, details: str) -> None:
        self.moss_status.setText("MOSS-TTS startup preload failed; Render will retry.")
        self.moss_timing_label.setText("Startup preload failed")
        self.append_log(self.moss_status.text() + "\n" + details)

    def on_moss_preload_finished(self) -> None:
        self.set_busy(False)
        self.preload_worker = None
        self.preload_thread = None

    def align_left_form(self, form: QFormLayout) -> None:
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setHorizontalSpacing(10)
        for row in range(form.rowCount()):
            item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            if item and item.widget():
                item.widget().setFixedWidth(105)
                item.widget().setAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )

    def icon_button(self, icon: QStyle.StandardPixmap, tooltip: str, callback) -> QPushButton:
        button = QPushButton()
        button.setIcon(self.style().standardIcon(icon))
        button.setIconSize(QSize(16, 16))
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
        button.setFixedSize(30, 28)
        button.clicked.connect(callback)
        return button

    def with_browse(self, line_edit: QLineEdit, callback) -> QWidget:
        wrapper = QWidget()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(line_edit)
        layout.addWidget(self.button("Browse", callback))
        return wrapper

    def with_browse_and_copy(self, line_edit: QLineEdit, browse_callback, copy_callback) -> QWidget:
        wrapper = QWidget()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(line_edit, 1)
        layout.addWidget(self.button("Browse", browse_callback))
        layout.addWidget(self.button("Copy path", copy_callback))
        return wrapper

    def paired_controls(self, first: QWidget, second_label: str, second: QWidget, extra=None) -> QWidget:
        wrapper = QWidget()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(first, 2)
        label = QLabel(second_label)
        label.setMinimumWidth(label.sizeHint().width())
        layout.addWidget(label)
        layout.addWidget(second, 2)
        if extra is not None:
            layout.addWidget(extra)
        return wrapper

    def inline_controls(self, *widgets: QWidget) -> QWidget:
        wrapper = QWidget()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        for widget in widgets:
            layout.addWidget(widget)
        layout.addStretch()
        return wrapper

    def compact_controls(self, first: QWidget, *labeled_widgets: tuple[str, QWidget]) -> QWidget:
        wrapper = QWidget()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(first, 2)
        for label_text, widget in labeled_widgets:
            label = QLabel(label_text)
            label.setMinimumWidth(label.sizeHint().width())
            layout.addWidget(label)
            layout.addWidget(widget, 2)
        return wrapper

    def percent_slider_control(self, default: int, minimum: int = 0, maximum: int = 100) -> tuple[QWidget, QSlider, QLabel]:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(default)
        slider.setSingleStep(1)
        slider.setPageStep(5)
        value_label = QLabel(f"{default}%")
        value_label.setMinimumWidth(42)
        wrapper = QWidget()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(slider, 1)
        layout.addWidget(value_label)
        slider.valueChanged.connect(lambda value: value_label.setText(f"{value}%"))
        return wrapper, slider, value_label

    def set_deep_tooltip(self, widget: QWidget, tooltip: str) -> None:
        widget.setToolTip(tooltip)
        for child in widget.findChildren(QWidget):
            child.setToolTip(tooltip)

    def set_form_tooltips(self, form: QFormLayout, tooltips: dict[str, str]) -> None:
        for row in range(form.rowCount()):
            label_item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            field_item = form.itemAt(row, QFormLayout.ItemRole.FieldRole)
            label = label_item.widget() if label_item else None
            field = field_item.widget() if field_item else None
            label_text = label.text().rstrip(":") if isinstance(label, QLabel) else ""
            tooltip = tooltips.get(label_text)
            if tooltip:
                if label:
                    label.setToolTip(tooltip)
                if field:
                    self.set_deep_tooltip(field, tooltip)

    def create_caption_widgets(self) -> None:
        self.caption_video_file = QLineEdit(self.settings["caption_video_file"])
        self.caption_video_file.setPlaceholderText("Video or audio file for caption generation")
        self.caption_import_file = QLineEdit(self.settings.get("caption_import_file", ""))
        self.caption_import_file.setPlaceholderText("Optional existing .srt or .json caption/timing file")
        self.caption_output_dir = QLineEdit(self.settings["caption_output_dir"])
        self.caption_output_dir.setPlaceholderText("Folder for SRT / ASS / JSON / burned video")

        self.caption_mode = QComboBox()
        self.caption_mode.addItems(["Standard", "Pro Highlight"])
        self.caption_mode.setCurrentText(self.settings["caption_mode"])
        self.caption_engine = QComboBox()
        self.caption_engine.addItems(["faster-whisper", "stable-ts", "WhisperX"])
        self.caption_engine.setCurrentText(self.settings["caption_engine"])
        self.caption_render_engine = QComboBox()
        self.caption_render_engine.addItems(["Plain subtitle", "ASS karaoke", "Burn-in overlay"])
        self.caption_render_engine.setCurrentText(self.settings["caption_render_engine"])
        self.caption_device = QComboBox()
        self.caption_device.addItems(["Auto", "CPU", "GPU"])
        self.caption_device.setCurrentText(self.settings["caption_device"])
        self.caption_device.setToolTip(
            "Auto sẽ tự ưu tiên CUDA GPU khi có thể, sau đó tự fallback CPU nếu GPU không chạy được."
        )
        self.caption_word_timing = QCheckBox("Word timing")
        self.caption_word_timing.setChecked(setting_bool(self.settings, "caption_word_timing"))

        self.caption_language = QComboBox()
        self.caption_language.addItems(["Auto", "English", "Spanish"])
        self.caption_language.setCurrentText(self.settings["caption_language"])
        self.caption_model = QComboBox()
        self.caption_model.addItems(["small", "medium", "large-v3", "turbo"])
        self.caption_model.setCurrentText(self.settings["caption_model"])
        self.caption_accuracy = QComboBox()
        self.caption_accuracy.addItems(["Fast", "Balanced", "Best"])
        self.caption_accuracy.setCurrentText(self.settings["caption_accuracy"])
        self.caption_speed_preset = QComboBox()
        self.caption_speed_preset.addItems(["Fast GPU", "Balanced", "Quality"])
        self.caption_speed_preset.setCurrentText(self.settings.get("caption_speed_preset", "Fast GPU"))
        self.caption_speed_preset.setToolTip(
            "Fast GPU dùng preset NVENC nhanh hơn để giảm thời gian burn MP4. "
            "Quality giữ bitrate/encode chặt hơn nhưng chạy chậm hơn."
        )
        self.caption_transcribe_batch = QSpinBox()
        self.caption_transcribe_batch.setRange(1, 32)
        self.caption_transcribe_batch.setValue(setting_int(self.settings, "caption_transcribe_batch"))
        self.caption_transcribe_batch.setToolTip(
            "Batch lớn hơn giúp faster-whisper dùng GPU nhiều hơn. Nếu thiếu VRAM, giảm xuống 8 hoặc 4."
        )
        self.caption_workers = QSpinBox()
        self.caption_workers.setRange(1, 16)
        self.caption_workers.setValue(setting_int(self.settings, "caption_workers"))
        self.caption_workers.setToolTip(
            "Số worker cho faster-whisper và filter subtitle FFmpeg. Tăng giúp nhanh hơn nếu CPU/GPU còn dư."
        )
        self.caption_cuda_fix_button = self.button("Fix CUDA", self.install_caption_cuda_runtime)
        self.caption_cuda_fix_button.setToolTip(
            "Kiểm tra và cài CUDA runtime/cuBLAS/cuDNN cần cho faster-whisper chạy GPU."
        )
        self.caption_vad = QCheckBox("VAD filter")
        self.caption_vad.setChecked(True)
        self.caption_punctuation = QCheckBox("Punctuation")
        self.caption_punctuation.setChecked(True)
        self.caption_diarization = QCheckBox("Diarization")

        self.caption_preset = QComboBox()
        self.caption_preset.addItems(CAPTION_PRESET_ORDER)
        self.caption_preset.setCurrentText(self.settings["caption_preset"])
        self.caption_preset_note = QLabel("")
        self.caption_preset_note.setWordWrap(True)

        self.caption_font_family = QComboBox()
        self.caption_font_family.setEditable(True)
        self.caption_font_family.addItems(
            [
                "Verdana",
                "Tahoma",
                "Segoe UI",
                "Roboto",
                "Poppins",
                "Open Sans",
                "Montserrat",
                "Impact",
                "Bebas Neue",
                "Arial Black",
                "Arial",
                "Anton",
            ]
        )
        self.caption_font_size = QSpinBox()
        self.caption_font_size.setRange(24, 120)
        self.caption_bold = QCheckBox("Bold")
        self.caption_italic = QCheckBox("Italic")
        self.caption_uppercase = QCheckBox("Uppercase")
        self.caption_letter_spacing = QSpinBox()
        self.caption_letter_spacing.setRange(0, 20)
        self.caption_line_spacing = QDoubleSpinBox()
        self.caption_line_spacing.setRange(0.8, 2.0)
        self.caption_line_spacing.setSingleStep(0.1)
        self.caption_line_spacing.setValue(1.0)
        self.caption_max_words = QSpinBox()
        self.caption_max_words.setRange(1, 12)
        self.caption_max_words.setValue(4)
        self.caption_max_chars = QSpinBox()
        self.caption_max_chars.setRange(8, 60)
        self.caption_max_chars.setValue(18)
        self.caption_two_line = QCheckBox("Two-line mode")
        self.caption_two_line.setChecked(True)

        self.caption_base_color_widget, self.caption_base_color = self.color_control("#FFFFFF")
        self.caption_active_color_widget, self.caption_active_color = self.color_control("#FF8A00")
        self.caption_outline_color_widget, self.caption_outline_color = self.color_control("#000000")
        self.caption_shadow_color_widget, self.caption_shadow_color = self.color_control("#000000")
        self.caption_inactive_dim_widget, self.caption_inactive_dim, self.caption_inactive_dim_label = (
            self.percent_slider_control(100, 20, 100)
        )

        self.caption_outline_width = QSpinBox()
        self.caption_outline_width.setRange(0, 12)
        self.caption_shadow_enable = QCheckBox("Shadow")
        self.caption_shadow_x = QSpinBox()
        self.caption_shadow_x.setRange(-20, 20)
        self.caption_shadow_x.setValue(2)
        self.caption_shadow_y = QSpinBox()
        self.caption_shadow_y.setRange(-20, 20)
        self.caption_shadow_y.setValue(2)
        self.caption_glow_enable = QCheckBox("Pseudo glow")
        self.caption_glow_strength = QSpinBox()
        self.caption_glow_strength.setRange(0, 10)

        self.caption_background_mode = QComboBox()
        self.caption_background_mode.addItems(["None", "Line box", "Active word box"])
        self.caption_background_color_widget, self.caption_background_color = self.color_control("#000000")
        self.caption_background_opacity_widget, self.caption_background_opacity, self.caption_background_opacity_label = (
            self.percent_slider_control(45, 0, 100)
        )
        self.caption_padding_x = QSpinBox()
        self.caption_padding_x.setRange(0, 80)
        self.caption_padding_x.setValue(16)
        self.caption_padding_y = QSpinBox()
        self.caption_padding_y.setRange(0, 60)
        self.caption_padding_y.setValue(8)
        self.caption_corner_radius = QSpinBox()
        self.caption_corner_radius.setRange(0, 40)
        self.caption_corner_radius.setValue(12)

        self.caption_highlight_type = QComboBox()
        self.caption_highlight_type.addItems(["None", "Active color", "Active background", "Progressive sweep"])
        self.caption_highlight_transition = QComboBox()
        self.caption_highlight_transition.addItems(["Instant", "Smooth", "Sweep"])
        self.caption_reveal_words = QCheckBox("Reveal words one-by-one")
        self.caption_fade_words = QCheckBox("Fade in words")
        self.caption_pop_active = QCheckBox("Pop active word")
        self.caption_scale_active = QSpinBox()
        self.caption_scale_active.setRange(80, 140)
        self.caption_scale_active.setSuffix("%")
        self.caption_scale_active.setValue(100)

        self.caption_anchor = QComboBox()
        self.caption_anchor.addItems(["Bottom", "Middle", "Top"])
        self.caption_alignment = QComboBox()
        self.caption_alignment.addItems(["Left", "Center", "Right"])
        self.caption_margin_bottom = QSpinBox()
        self.caption_margin_bottom.setRange(0, 400)
        self.caption_margin_x = QSpinBox()
        self.caption_margin_x.setRange(0, 400)
        self.caption_margin_x.setValue(60)
        self.caption_safe_area = QCheckBox("Safe area preview")
        self.caption_safe_area.setChecked(True)
        self.caption_youtube_auto = QCheckBox("YouTube Auto Position")
        self.caption_youtube_auto.setChecked(setting_bool(self.settings, "caption_youtube_auto"))

        self.caption_min_duration = QDoubleSpinBox()
        self.caption_min_duration.setRange(0.1, 5.0)
        self.caption_min_duration.setSingleStep(0.1)
        self.caption_min_duration.setValue(0.8)
        self.caption_min_duration.setSuffix(" sec")
        self.caption_max_duration = QDoubleSpinBox()
        self.caption_max_duration.setRange(0.5, 10.0)
        self.caption_max_duration.setSingleStep(0.1)
        self.caption_max_duration.setValue(3.0)
        self.caption_max_duration.setSuffix(" sec")
        self.caption_word_grouping = QComboBox()
        self.caption_word_grouping.addItems(["By punctuation", "By max words", "By duration"])

        self.caption_export_srt = QCheckBox("SRT")
        self.caption_export_srt.setChecked(True)
        self.caption_export_vtt = QCheckBox("VTT")
        self.caption_export_ass = QCheckBox("ASS")
        self.caption_export_json = QCheckBox("JSON")
        self.caption_export_json.setChecked(True)
        self.caption_burn_video = QCheckBox("Burned-in MP4")
        self.caption_burn_video.setChecked(setting_bool(self.settings, "caption_burn_video"))
        self.caption_filename_pattern = QLineEdit("{video_name}_caption_{mode}")
        self.caption_render_button = self.button("Render captions", self.render_caption)
        self.caption_stop_button = self.button("Stop", self.stop_caption_render)
        self.caption_open_output_button = self.button("Open output folder", self.open_caption_output_folder)
        self.caption_import_button = self.button("Import SRT/JSON", self.pick_caption_import_file)
        self.caption_save_config_button = self.button("Save config", self.save_caption_configuration)
        self.caption_load_defaults_button = self.button("Load defaults", self.load_default_caption_config)
        self.caption_stop_button.setEnabled(False)
        self.caption_progress = QProgressBar()
        self.caption_progress.setRange(0, 100)
        self.caption_progress.setValue(0)
        self.caption_elapsed = QLabel("Elapsed 00:00:00 | 0%")

        self.caption_preview = CaptionPreviewWidget()
        self.caption_config_preview = QPlainTextEdit()
        self.caption_config_preview.setReadOnly(True)
        self.caption_config_preview.setMaximumBlockCount(1000)
        self.caption_status = QLabel("Caption tab ready. Render will transcribe the source when no SRT/JSON is imported.")
        self.caption_status.setWordWrap(True)
        self.caption_status.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.caption_status.setMinimumWidth(0)
        self.caption_process: subprocess.Popen | None = None
        self.caption_transcribe_job: multiprocessing.Process | None = None
        self.caption_cancel_requested = False
        self.caption_batch_rows: list[dict] = []

        self.apply_caption_preset(self.caption_preset.currentText(), update_combo=False)

    def create_watermark_widgets(self) -> None:
        s = self.settings
        self.watermark_input_files = QListWidget()
        self.watermark_input_files.setMaximumHeight(112)
        self.watermark_input_files.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        for source_path in str(s["watermark_input_files"]).splitlines():
            if source_path.strip():
                self.add_watermark_input_path(source_path.strip())
        self.watermark_names = QPlainTextEdit(s["watermark_names"])
        self.watermark_names.setPlaceholderText("One logo / channel name per line")
        self.watermark_names.setMaximumHeight(80)
        self.watermark_trailer_video = QLineEdit(s.get("watermark_trailer_video", ""))
        self.watermark_trailer_video.setPlaceholderText("Optional: trailer inserted before source video")
        self.watermark_trailer_video.setToolTip(
            "Video trailer sẽ được chèn vào đầu trước video gốc. Nếu có trailer, warning image sẽ overlay trên trailer."
        )
        self.watermark_trailer_video.setStyleSheet(
            "QLineEdit { background: #241b10; border: 1px solid #f0a020; color: #ffe6b0; }"
        )
        self.watermark_transition_duration = QDoubleSpinBox()
        self.watermark_transition_duration.setRange(0.05, 5.0)
        self.watermark_transition_duration.setDecimals(2)
        self.watermark_transition_duration.setSuffix(" sec")
        self.watermark_transition_duration.setValue(float(s.get("watermark_transition_duration", "0.50")))
        self.watermark_output_dir = QLineEdit(s["watermark_output_dir"])
        self.watermark_position = QComboBox()
        self.watermark_position.addItems(["Top Left", "Top Right", "Bottom Left", "Bottom Right"])
        self.watermark_position.setCurrentText(s["watermark_position"])
        self.watermark_name_start = QDoubleSpinBox()
        self.watermark_name_start.setRange(0, 86400)
        self.watermark_name_start.setDecimals(2)
        self.watermark_name_start.setSuffix(" sec")
        self.watermark_name_start.setValue(float(s.get("watermark_name_start", "0.0")))
        self.watermark_padding_x = QSpinBox()
        self.watermark_padding_x.setRange(0, 500)
        self.watermark_padding_x.setValue(setting_int(s, "watermark_padding_x"))
        self.watermark_padding_y = QSpinBox()
        self.watermark_padding_y.setRange(0, 500)
        self.watermark_padding_y.setValue(setting_int(s, "watermark_padding_y"))
        self.watermark_font = QComboBox()
        self.watermark_font.setEditable(True)
        self.watermark_font.addItems(["Arial", "Montserrat", "Roboto", "Tahoma", "Verdana"])
        self.watermark_font.setCurrentText(s["watermark_font"])
        self.watermark_font_size = QSpinBox()
        self.watermark_font_size.setRange(10, 240)
        self.watermark_font_size.setValue(setting_int(s, "watermark_font_size"))
        self.watermark_bold = QCheckBox("Bold")
        self.watermark_bold.setChecked(setting_bool(s, "watermark_bold"))
        self.watermark_italic = QCheckBox("Italic")
        self.watermark_italic.setChecked(setting_bool(s, "watermark_italic"))
        self.watermark_text_color_widget, self.watermark_text_color = self.color_control(s["watermark_text_color"])
        self.watermark_background = QComboBox()
        self.watermark_background.addItems(["None", "Square", "Round", "Much rounded"])
        self.watermark_background.setCurrentText("Round" if s["watermark_background"] == "Rounded" else s["watermark_background"])
        self.watermark_background_color_widget, self.watermark_background_color = self.color_control(
            s["watermark_background_color"]
        )
        self.watermark_background_opacity_widget, self.watermark_background_opacity, self.watermark_background_opacity_label = (
            self.percent_slider_control(setting_int(s, "watermark_background_opacity"), 0, 100)
        )
        self.watermark_warning_image = QLineEdit(s["watermark_warning_image"])
        self.watermark_warning_duration = QDoubleSpinBox()
        self.watermark_warning_duration.setRange(0.05, 30)
        self.watermark_warning_duration.setDecimals(2)
        self.watermark_warning_duration.setSuffix(" sec")
        self.watermark_warning_duration.setValue(float(s["watermark_warning_duration"]))
        self.watermark_warning_fit = QComboBox()
        self.watermark_warning_fit.addItems(["Crop", "Stretch"])
        self.watermark_warning_fit.setCurrentText(s["watermark_warning_fit"])
        self.watermark_subscribe_video = QLineEdit(s["watermark_subscribe_video"])
        self.watermark_subscribe_start = QDoubleSpinBox()
        self.watermark_subscribe_start.setRange(0, 86400)
        self.watermark_subscribe_start.setSuffix(" sec")
        self.watermark_subscribe_start.setFixedWidth(96)
        self.watermark_subscribe_start.setValue(float(s["watermark_subscribe_start"]))
        self.watermark_subscribe_interval = QDoubleSpinBox()
        self.watermark_subscribe_interval.setRange(0.1, 86400)
        self.watermark_subscribe_interval.setValue(float(s["watermark_subscribe_interval"]))
        self.watermark_subscribe_count = QSpinBox()
        self.watermark_subscribe_count.setRange(1, 100)
        self.watermark_subscribe_count.setValue(setting_int(s, "watermark_subscribe_count"))
        self.watermark_subscribe_schedule_note = QLabel(
            "3 shows: custom | middle | 20s before end | 1s bell"
        )
        self.watermark_subscribe_schedule_note.setStyleSheet(
            "color: #ffb84d; font-weight: 600;"
        )
        self.watermark_subscribe_position = QComboBox()
        self.watermark_subscribe_position.addItems(["Top Left", "Top Right", "Bottom Left", "Bottom Right"])
        self.watermark_subscribe_position.setCurrentText(s["watermark_subscribe_position"])
        self.watermark_subscribe_scale = QSpinBox()
        self.watermark_subscribe_scale.setRange(5, 100)
        self.watermark_subscribe_scale.setSuffix("%")
        self.watermark_subscribe_scale.setValue(setting_int(s, "watermark_subscribe_scale"))
        self.watermark_chroma_key = QCheckBox("Remove green screen (chroma key)")
        self.watermark_chroma_key.setChecked(setting_bool(s, "watermark_chroma_key"))
        self.watermark_chroma_color_widget, self.watermark_chroma_color = self.color_control(s["watermark_chroma_color"])
        self.watermark_chroma_similarity = QDoubleSpinBox()
        self.watermark_chroma_similarity.setRange(0, 1)
        self.watermark_chroma_similarity.setSingleStep(0.01)
        self.watermark_chroma_similarity.setValue(float(s["watermark_chroma_similarity"]))
        self.watermark_chroma_blend = QDoubleSpinBox()
        self.watermark_chroma_blend.setRange(0, 1)
        self.watermark_chroma_blend.setSingleStep(0.01)
        self.watermark_chroma_blend.setValue(float(s["watermark_chroma_blend"]))
        self.watermark_chroma_screenshot = ChromaColorPickerLabel()
        self.watermark_chroma_screenshot.colorPicked.connect(self.pick_watermark_chroma_from_image)
        self.watermark_codec = QComboBox()
        self.watermark_codec.addItems(["auto", "h264_nvenc", "hevc_nvenc", "h264_qsv", "h264_amf"])
        self.watermark_codec.setCurrentText(s["watermark_codec"])
        self.watermark_crf = QSpinBox()
        self.watermark_crf.setRange(0, 40)
        self.watermark_crf.setValue(setting_int(s, "watermark_crf"))
        self.watermark_preview = WatermarkPreviewWidget()
        self.watermark_status = QLabel("Watermark tab ready.")
        self.watermark_status.setWordWrap(True)
        self.watermark_progress = QProgressBar()
        self.watermark_render_button = self.button("Render batch", self.render_watermark)
        self.watermark_stop_button = self.button("Stop", self.stop_watermark)
        self.watermark_stop_button.setEnabled(False)
        self.watermark_open_folder_button = self.button("Open folder", self.open_watermark_output_folder)
        self.watermark_thread: QThread | None = None
        self.watermark_worker: WatermarkWorker | None = None
        self.watermark_render_started: float | None = None

    def build_watermark_tab(self) -> QWidget:
        source_form = QFormLayout()
        source_videos_widget = QWidget()
        source_videos_layout = QHBoxLayout(source_videos_widget)
        source_videos_layout.setContentsMargins(0, 0, 0, 0)
        source_videos_layout.setSpacing(8)
        source_videos_layout.addWidget(self.watermark_input_files, 1)
        source_videos_layout.addWidget(self.button("Add videos", self.pick_watermark_inputs))
        source_form.addRow("Source videos", source_videos_widget)
        source_form.addRow("Channel names", self.watermark_names)
        source_form.addRow(
            "⚠ Trailer video",
            self.with_browse_and_copy(
                self.watermark_trailer_video,
                self.pick_watermark_trailer,
                self.copy_watermark_trailer_path,
            ),
        )
        source_form.addRow("Trailer transition", self.watermark_transition_duration)
        source_form.addRow("Output folder", self.with_browse(self.watermark_output_dir, self.pick_watermark_output))
        source = QGroupBox("Batch input (every video × every channel name)")
        source.setLayout(source_form)
        text_form = QFormLayout()
        text_form.addRow("Position / style", self.paired_controls(
            self.watermark_position, "Style", self.inline_controls(self.watermark_bold, self.watermark_italic)
        ))
        text_form.addRow("Channel name starts", self.compact_controls(
            self.watermark_name_start,
            ("Edge padding X", self.watermark_padding_x),
            ("Y", self.watermark_padding_y),
        ))
        text_form.addRow("Font", self.compact_controls(
            self.watermark_font,
            ("Size", self.watermark_font_size),
            ("Text color", self.watermark_text_color_widget),
        ))
        text_form.addRow("Background", self.compact_controls(
            self.watermark_background,
            ("Background color", self.watermark_background_color_widget),
            ("Opacity", self.watermark_background_opacity_widget),
        ))
        text_group = QGroupBox("Channel name style")
        text_group.setLayout(text_form)
        warning_form = QFormLayout()
        warning_form.addRow("Warning image", self.with_browse(self.watermark_warning_image, self.pick_watermark_warning))
        warning_form.addRow("Display duration", self.paired_controls(self.watermark_warning_duration, "Fit", self.watermark_warning_fit))
        warning_group = QGroupBox("Opening warning (optional)")
        warning_group.setLayout(warning_form)
        sub_form = QFormLayout()
        sub_form.addRow("Subscribe video", self.with_browse(self.watermark_subscribe_video, self.pick_watermark_subscribe))
        subscribe_schedule_row = QWidget()
        subscribe_schedule_layout = QHBoxLayout(subscribe_schedule_row)
        subscribe_schedule_layout.setContentsMargins(0, 0, 0, 0)
        subscribe_schedule_layout.setSpacing(8)
        first_show_widget = QWidget()
        first_show_layout = QHBoxLayout(first_show_widget)
        first_show_layout.setContentsMargins(0, 0, 0, 0)
        first_show_layout.setSpacing(8)
        first_show_layout.addWidget(QLabel("First show at"))
        first_show_layout.addWidget(self.watermark_subscribe_start)
        first_show_layout.addStretch()
        subscribe_schedule_layout.addWidget(first_show_widget, 1)
        subscribe_schedule_layout.addWidget(self.watermark_subscribe_schedule_note, 2)
        sub_form.addRow(subscribe_schedule_row)
        sub_form.addRow("Position / scale", self.paired_controls(self.watermark_subscribe_position, "Scale", self.watermark_subscribe_scale))
        sub_form.addRow("Chroma key", self.compact_controls(
            self.watermark_chroma_key,
            ("Key color", self.watermark_chroma_color_widget),
        ))
        sub_form.addRow("Key tuning", self.paired_controls(self.watermark_chroma_similarity, "Blend", self.watermark_chroma_blend))
        sub_form.addRow("Color sampler", self.compact_controls(
            self.watermark_chroma_screenshot,
            ("", self.button("Capture frame", self.capture_watermark_chroma_frame)),
        ))
        sub_group = QGroupBox("YouTube subscribe overlay (optional)")
        sub_group.setLayout(sub_form)
        render_form = QFormLayout()
        render_form.addRow("Fast encoder", self.paired_controls(self.watermark_codec, "Quality", self.watermark_crf))
        render_form.addRow("Settings", self.inline_controls(
            self.button("Save settings", self.save_watermark_settings),
            self.button("Load defaults", self.load_watermark_defaults),
            self.button("Import settings", self.import_watermark_settings)))
        render_group = QGroupBox("Render and settings")
        render_group.setLayout(render_form)
        left = QWidget()
        left.setMinimumWidth(560)
        left_layout = QVBoxLayout(left)
        for group in (source, text_group, warning_group, sub_group, render_group):
            left_layout.addWidget(group)
        left_layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(left)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel("Realtime placement preview"))
        right_layout.addWidget(self.watermark_preview)
        right_layout.addWidget(self.watermark_progress)
        right_layout.addWidget(self.watermark_status)
        right_layout.addStretch()
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(scroll)
        splitter.addWidget(right)
        splitter.setSizes([600, 680])
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(splitter)
        layout.addLayout(self.inline_layout(
            self.watermark_render_button, self.watermark_stop_button, self.watermark_open_folder_button
        ))
        return tab

    def create_tools_widgets(self) -> None:
        self.tools_trailer_path = QLineEdit(self.watermark_trailer_video.text())
        self.tools_trailer_path.setPlaceholderText("Select a trailer video generated by Gemini")
        self.tools_logo_size = QSpinBox()
        self.tools_logo_size.setRange(4, 20)
        self.tools_logo_size.setValue(15)
        self.tools_logo_size.setSuffix("%")
        self.tools_logo_margin = QSpinBox()
        self.tools_logo_margin.setRange(0, 10)
        self.tools_logo_margin.setValue(10)
        self.tools_logo_margin.setSuffix("%")
        self.tools_before_preview = VideoMaskLabel("Before")
        self.tools_after_preview = QLabel("After")
        for preview in (self.tools_before_preview, self.tools_after_preview):
            preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
            preview.setMinimumSize(360, 220)
            preview.setStyleSheet("QLabel { background: #090d14; border: 1px solid #344055; }")
        self.tools_preview_time = QLabel(
            "Run Analyze & Preview to locate the strongest logo frame."
        )
        self.tools_preview_time.setWordWrap(True)
        self.tools_status = QLabel("Tools ready.")
        self.tools_status.setWordWrap(True)
        self.tools_progress = QProgressBar()
        self.tools_analyze_button = self.button("Analyze & Preview", self.analyze_gemini_logo)
        self.tools_view_temporal_button = self.button(
            "View Stable Clean", self.view_temporal_video
        )
        self.tools_view_lama_button = self.button("View LaMa Fallback", self.view_lama_video)
        self.tools_use_temporal_button = self.button(
            "Use Stable Clean for Watermark", self.use_temporal_video
        )
        self.tools_use_lama_button = self.button(
            "Use LaMa Fallback for Watermark", self.use_lama_video
        )
        self.tools_temporal_rerun_button = self.button(
            "Run Stable Clean", self.rerun_temporal
        )
        self.tools_lama_rerun_button = self.button(
            "Rerun LaMa with Current Mask", self.rerun_lama
        )
        self.tools_temporal_rerun_button.setToolTip(
            "Scene-aware LaMa anchors with bidirectional optical flow."
        )
        self.tools_lama_rerun_button.setToolTip(
            "Render an independent frame-by-frame LaMa version from the original video "
            "using the current mask; it may flicker on motion and scene transitions."
        )
        for button in (
            self.tools_view_temporal_button, self.tools_view_lama_button,
            self.tools_use_temporal_button, self.tools_use_lama_button,
            self.tools_temporal_rerun_button, self.tools_lama_rerun_button,
        ):
            button.setEnabled(False)
        self.tools_mask_output = ""
        self.tools_alpha_output = ""
        self.tools_temporal_output = ""
        self.tools_lama_output = ""
        self.tools_manual_box: tuple[int, int, int, int] | None = None
        self.tools_preview_source = ""
        self.tools_preview_time_value = 0.0
        self.tools_before_preview.maskChanged.connect(self.on_tools_mask_changed)
        self.tools_thread: QThread | None = None
        self.tools_worker: GeminiLogoWorker | None = None
        self.tools_started_at: float | None = None
        self.tools_status_message = "Tools ready."
        self.tools_elapsed_timer = QTimer(self)
        self.tools_elapsed_timer.setInterval(1000)
        self.tools_elapsed_timer.timeout.connect(self.update_tools_elapsed_status)
        self.missed_storyboard_images_dir = QLineEdit()
        self.missed_storyboard_images_dir.setPlaceholderText(
            "Select the image folder to check sequence numbers"
        )
        self.missed_storyboard_prompt_file = QLineEdit()
        self.missed_storyboard_prompt_file.setPlaceholderText(
            "Select the storyboard prompt TXT file"
        )
        self.missed_storyboard_status = QLabel(
            "Ready to check the image folder and storyboard prompt."
        )
        self.missed_storyboard_status.setWordWrap(True)
        self.missed_storyboard_log = TranslatedLogEdit()
        self.missed_storyboard_log.setReadOnly(True)
        self.missed_storyboard_log.setMinimumHeight(220)
        self.missed_storyboard_check_button = self.button(
            "Check Missing Images", self.check_missed_storyboard_images
        )
        self.missed_storyboard_create_button = self.button(
            "Create Selected Prompts TXT", self.create_missed_storyboard_prompt_file
        )
        self.missed_storyboard_add_row_button = self.button(
            "+ Add 10 Numbers", self.add_missed_storyboard_number_row
        )
        self.missed_storyboard_clear_selection_button = self.button(
            "Clear Selection", self.clear_missed_storyboard_number_selection
        )
        self.missed_storyboard_toggle_table_button = self.button(
            "Hide Number Table", self.toggle_missed_storyboard_number_table
        )
        self.missed_storyboard_selection_label = QLabel("Selected: 0 number(s)")
        self.missed_storyboard_number_table = QTableWidget(0, 10)
        self.missed_storyboard_number_table.horizontalHeader().setVisible(False)
        self.missed_storyboard_number_table.verticalHeader().setVisible(False)
        self.missed_storyboard_number_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.missed_storyboard_number_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.missed_storyboard_number_table.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self.missed_storyboard_number_table.setMinimumHeight(360)
        self.missed_storyboard_number_checks: dict[int, QCheckBox] = {}
        for _ in range(10):
            self.add_missed_storyboard_number_row()
        self.missed_storyboard_open_button = self.button(
            "Open Output Folder", self.open_missed_storyboard_output
        )
        self.missed_storyboard_open_button.setEnabled(False)
        self.missed_storyboard_output = ""
        self.missed_storyboard_missing_numbers: list[int] = []

    def build_tools_tab(self) -> QWidget:
        tabs = QTabWidget()
        tabs.addTab(self.build_remove_video_logo_tab(), "Remove video logo")
        tabs.addTab(
            self.build_update_missed_storyboard_prompts_tab(),
            "Update missed storyboard prompts",
        )
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(tabs)
        return tab

    def build_remove_video_logo_tab(self) -> QWidget:
        trailer_form = QFormLayout()
        trailer_form.addRow(
            "Trailer video",
            self.with_browse(self.tools_trailer_path, self.pick_tools_trailer),
        )
        trailer_form.addRow(
            "Logo region",
            self.paired_controls(self.tools_logo_size, "Inner margin", self.tools_logo_margin),
        )
        trailer_form.addRow(
            "Actions",
            self.inline_controls(
                self.tools_analyze_button,
                self.tools_temporal_rerun_button,
                self.tools_lama_rerun_button,
            ),
        )
        trailer_group = QGroupBox("Gemini trailer · Remove bottom-right logo")
        trailer_group.setLayout(trailer_form)
        preview_row = QHBoxLayout()
        preview_row.addWidget(self.tools_before_preview)
        preview_row.addWidget(self.tools_after_preview)
        preview_group = QGroupBox("Worst detected shot · Before / After")
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.addLayout(preview_row)
        preview_layout.addWidget(self.tools_preview_time)
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(trailer_group)
        layout.addWidget(preview_group, 1)
        layout.addWidget(self.tools_progress)
        layout.addWidget(self.tools_status)
        layout.addLayout(self.inline_layout(
            self.tools_view_temporal_button, self.tools_view_lama_button,
        ))
        layout.addLayout(self.inline_layout(
            self.tools_use_temporal_button, self.tools_use_lama_button,
        ))
        return tab

    def build_update_missed_storyboard_prompts_tab(self) -> QWidget:
        form = QFormLayout()
        form.addRow(
            "Storyboard prompt TXT",
            self.with_browse(
                self.missed_storyboard_prompt_file,
                self.pick_missed_storyboard_prompt_file,
            ),
        )
        form.addRow(
            "Image folder",
            self.with_browse(
                self.missed_storyboard_images_dir,
                self.pick_missed_storyboard_images_dir,
            ),
        )
        input_group = QGroupBox("Inputs")
        input_group.setLayout(form)

        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(input_group)
        self.missed_storyboard_number_group = QGroupBox("Select storyboard prompt numbers")
        number_layout = QVBoxLayout(self.missed_storyboard_number_group)
        number_layout.addWidget(self.missed_storyboard_number_table)
        number_layout.addLayout(
            self.inline_layout(
                self.missed_storyboard_add_row_button,
                self.missed_storyboard_clear_selection_button,
                self.missed_storyboard_selection_label,
            )
        )
        layout.addWidget(self.missed_storyboard_toggle_table_button)
        layout.addWidget(self.missed_storyboard_number_group)
        layout.addLayout(
            self.inline_layout(
                self.missed_storyboard_check_button,
                self.missed_storyboard_create_button,
                self.missed_storyboard_open_button,
            )
        )
        layout.addWidget(self.missed_storyboard_status)
        layout.addWidget(QLabel("Log"))
        layout.addWidget(self.missed_storyboard_log, 1)
        return tab

    def add_missed_storyboard_number_row(self) -> None:
        row = self.missed_storyboard_number_table.rowCount()
        self.missed_storyboard_number_table.insertRow(row)
        self.missed_storyboard_number_table.setRowHeight(row, 34)
        first_number = row * 10 + 1
        for column in range(10):
            number = first_number + column
            checkbox = QCheckBox(str(number))
            checkbox.setToolTip(f"Include storyboard prompt {number}")
            checkbox.stateChanged.connect(self.update_missed_storyboard_selection_label)
            container = QWidget()
            cell_layout = QHBoxLayout(container)
            cell_layout.setContentsMargins(6, 0, 2, 0)
            cell_layout.addWidget(checkbox)
            cell_layout.addStretch()
            self.missed_storyboard_number_table.setCellWidget(row, column, container)
            self.missed_storyboard_number_checks[number] = checkbox

    def selected_missed_storyboard_numbers(self) -> list[int]:
        return sorted(
            number for number, checkbox in self.missed_storyboard_number_checks.items()
            if checkbox.isChecked()
        )

    def update_missed_storyboard_selection_label(self, _state: int = 0) -> None:
        selected = self.selected_missed_storyboard_numbers()
        self.missed_storyboard_selection_label.setText(
            f"Selected: {len(selected)} number(s)"
        )

    def clear_missed_storyboard_number_selection(self) -> None:
        for checkbox in self.missed_storyboard_number_checks.values():
            checkbox.setChecked(False)
        self.update_missed_storyboard_selection_label()

    def toggle_missed_storyboard_number_table(self) -> None:
        visible = self.missed_storyboard_number_group.isHidden()
        self.missed_storyboard_number_group.setVisible(visible)
        self.missed_storyboard_toggle_table_button.setText(
            "Hide Number Table" if visible else "Show Number Table"
        )

    def pick_missed_storyboard_images_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Images folder")
        if path:
            self.missed_storyboard_images_dir.setText(path)
            self.check_missed_storyboard_images()

    def pick_missed_storyboard_prompt_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Storyboard prompt TXT",
            self.missed_storyboard_prompt_file.text(),
            "Text files (*.txt);;All files (*.*)",
        )
        if path:
            self.missed_storyboard_prompt_file.setText(path)

    def missed_storyboard_log_message(self, message: str) -> None:
        log_event("UI | Missed storyboard prompts | " + message)
        self.missed_storyboard_log.appendPlainText(message)
        scrollbar = self.missed_storyboard_log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def check_missed_storyboard_images(self) -> list[int]:
        folder_text = self.missed_storyboard_images_dir.text().strip()
        prompt_text = self.missed_storyboard_prompt_file.text().strip()
        self.missed_storyboard_missing_numbers = []
        if self.missed_storyboard_log.toPlainText().strip():
            self.missed_storyboard_log.appendPlainText("")
        if not prompt_text:
            self.missed_storyboard_status.setText("Storyboard prompt TXT is empty.")
            self.missed_storyboard_log_message("Image sequence check | Storyboard prompt TXT is empty.")
            return []
        prompt_path = Path(prompt_text)
        if not prompt_path.is_file():
            self.missed_storyboard_status.setText(f"Storyboard prompt TXT does not exist: {prompt_text}")
            self.missed_storyboard_log_message(
                f"Image sequence check | Storyboard prompt TXT does not exist: {prompt_text}"
            )
            return []
        try:
            prompt_blocks = self.parse_storyboard_prompt_blocks(
                prompt_path.read_text(encoding="utf-8-sig")
            )
        except UnicodeDecodeError:
            prompt_blocks = self.parse_storyboard_prompt_blocks(
                prompt_path.read_text(encoding="utf-8", errors="replace")
            )
        if not prompt_blocks:
            self.missed_storyboard_status.setText("No numbered storyboard prompt blocks found.")
            self.missed_storyboard_log_message(
                "Image sequence check | No numbered storyboard prompt blocks found."
            )
            return []
        expected_max = max(prompt_blocks)
        if not folder_text:
            self.missed_storyboard_status.setText("Image folder is empty.")
            self.missed_storyboard_log_message("Image sequence check | Images folder is empty.")
            return []
        folder = Path(folder_text)
        if not folder.is_dir():
            self.missed_storyboard_status.setText(f"Folder does not exist: {folder_text}")
            self.missed_storyboard_log_message(
                f"Image sequence check | Folder does not exist: {folder_text}"
            )
            return []

        image_files = self.list_media_files(folder, VIDEO_IMAGE_EXTS, recursive=False)
        ignored: list[str] = []
        number_to_files: dict[int, list[str]] = {}
        for path in image_files:
            number = self.extract_media_sequence_number(path.name, "image")
            if number is None:
                ignored.append(path.name)
                continue
            number_to_files.setdefault(number, []).append(path.name)
        if not number_to_files:
            self.missed_storyboard_status.setText(
                f"Found {len(image_files)} image file(s), but no sequence numbers."
            )
            self.missed_storyboard_log_message(
                f"Image sequence check | {len(image_files)} image file(s), "
                "no leading numbers found."
            )
            return []

        existing_numbers = set(number_to_files)
        missing_numbers = [
            number for number in range(1, expected_max + 1)
            if number not in existing_numbers
        ]
        duplicate_numbers = {
            number: sorted(files)
            for number, files in sorted(number_to_files.items())
            if len(files) > 1
        }
        self.missed_storyboard_missing_numbers = missing_numbers
        self.missed_storyboard_log_message(
            "Image sequence check | "
            f"{sum(len(files) for files in number_to_files.values())}/{len(image_files)} "
            f"numbered image file(s), range 1 -> {expected_max}."
        )
        if missing_numbers:
            missing_text = ", ".join(str(number) for number in missing_numbers)
            self.missed_storyboard_log_message(
                f"Missing image numbers: {len(missing_numbers)} images"
            )
            self.missed_storyboard_log_message(f"Missed images: {missing_text}")
            self.missed_storyboard_status.setText(
                f"Found {len(missing_numbers)} missing image number(s). See Log for details."
            )
        else:
            self.missed_storyboard_log_message("Missing image numbers: none.")
            self.missed_storyboard_status.setText("No missing image numbers found.")
        if duplicate_numbers:
            duplicate_text = "; ".join(
                f"{number}: {len(files)} files"
                for number, files in duplicate_numbers.items()
            )
            self.missed_storyboard_log_message(f"Duplicate image numbers: {duplicate_text}")
        if ignored:
            self.missed_storyboard_log_message(
                "Ignored image files without a sequence number: "
                f"{len(ignored)}"
            )
        return missing_numbers

    @staticmethod
    def parse_storyboard_prompt_blocks(text: str) -> dict[int, str]:
        pattern = re.compile(
            r"(?ms)^\s*(\d+)\s*(?:[.)\]:-]|\s)\s*(.*?)(?=^\s*\d+\s*(?:[.)\]:-]|\s)\s*|\Z)"
        )
        blocks: dict[int, str] = {}
        for match in pattern.finditer(text):
            number = int(match.group(1))
            block = match.group(0).strip()
            if block:
                blocks[number] = block
        return blocks

    def missed_storyboard_output_path(self, prompt_path: Path) -> Path:
        candidate = prompt_path.with_name(f"{prompt_path.stem}_selected_prompts{prompt_path.suffix}")
        number = 2
        while candidate.exists():
            candidate = prompt_path.with_name(
                f"{prompt_path.stem}_selected_prompts_{number}{prompt_path.suffix}"
            )
            number += 1
        return candidate

    def create_missed_storyboard_prompt_file(self) -> None:
        try:
            selected_numbers = self.selected_missed_storyboard_numbers()
            if not selected_numbers:
                raise ValueError("Select at least one number in the table.")
            prompt_path = Path(self.missed_storyboard_prompt_file.text().strip())
            if not prompt_path.is_file():
                raise ValueError("The storyboard prompt TXT file does not exist.")
            text = prompt_path.read_text(encoding="utf-8-sig")
            blocks = self.parse_storyboard_prompt_blocks(text)
            selected_blocks = [
                blocks[number]
                for number in selected_numbers
                if number in blocks
            ]
            selected_without_prompt = [
                number
                for number in selected_numbers
                if number not in blocks
            ]
            if not selected_blocks:
                raise ValueError(
                    "No storyboard prompt blocks match the selected numbers."
                )
            output_path = self.missed_storyboard_output_path(prompt_path)
            output_path.write_text("\n\n".join(selected_blocks) + "\n", encoding="utf-8")
            self.missed_storyboard_output = str(output_path)
            self.missed_storyboard_open_button.setEnabled(True)
            self.missed_storyboard_status.setText(
                f"Created {len(selected_blocks)} selected prompt block(s): {output_path}"
            )
            if self.missed_storyboard_log.toPlainText().strip():
                self.missed_storyboard_log.appendPlainText("")
            self.missed_storyboard_log_message(
                "Selected prompt export | "
                f"{len(selected_blocks)} block(s) -> {output_path}"
            )
            self.missed_storyboard_log_message(
                "Selected numbers: " + ", ".join(str(number) for number in selected_numbers)
            )
            if selected_without_prompt:
                self.missed_storyboard_log_message(
                    "Selected number(s) without storyboard prompt block: "
                    + ", ".join(str(number) for number in selected_without_prompt)
                )
        except Exception as exc:
            self.missed_storyboard_status.setText(str(exc))
            QMessageBox.warning(self, "Update missed storyboard prompts", str(exc))

    def open_missed_storyboard_output(self) -> None:
        path = Path(self.missed_storyboard_output)
        if not path.is_file():
            QMessageBox.information(
                self, "Update missed storyboard prompts",
                "No output file has been created yet."
            )
            return
        output_dir = path.parent
        if sys.platform == "win32":
            os.startfile(output_dir)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(output_dir)])
        else:
            subprocess.Popen(["xdg-open", str(output_dir)])

    def pick_tools_trailer(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Gemini trailer", self.tools_trailer_path.text(),
            "Video (*.mp4 *.mov *.mkv *.avi *.webm *.m4v)",
        )
        if path:
            self.tools_trailer_path.setText(path)

    def _tools_source(self) -> Path:
        source = Path(self.tools_trailer_path.text().strip())
        if not source.is_file():
            raise ValueError("The trailer video does not exist.")
        return gemini_original_source(source)

    def _tools_output(self, source: Path, method: str = "mask") -> Path:
        candidate = source.with_name(
            f"{source.stem}_no_gemini_logo_{method}{source.suffix}"
        )
        number = 2
        while candidate.exists():
            candidate = source.with_name(
                f"{source.stem}_no_gemini_logo_{method}_{number}{source.suffix}"
            )
            number += 1
        return candidate

    def analyze_gemini_logo(self) -> None:
        try:
            selected_source = Path(self.tools_trailer_path.text().strip())
            source = self._tools_source()
            width, height = media_video_size(str(source))
            search_region = (
                round(width * 0.56), round(height * 0.48),
                round(width * 0.43), round(height * 0.51),
            )
            detected_box, confidence, shot_time = detect_gemini_logo_in_video(
                str(source), search_region, sample_count=12
            )
            if detected_box is None:
                raise ValueError(
                    "Could not lock onto the logo consistently across multiple frames. "
                    "Check the video or draw a mask after selecting a suitable frame."
                )
            x, y, box_w, box_h = detected_box
            preview_dir = config_dir() / "tools_preview"
            preview_dir.mkdir(parents=True, exist_ok=True)
            before = preview_dir / "gemini_before.png"
            after = preview_dir / "gemini_after.png"
            common = [ffmpeg_executable(), "-y", "-hide_banner", "-loglevel", "error",
                      "-ss", f"{shot_time:.3f}", "-i", str(source), "-frames:v", "1"]
            subprocess.run([*common, str(before)], check=True,
                           creationflags=0x08000000 if sys.platform == "win32" else 0)
            subprocess.run(
                [
                    *common, "-vf",
                    f"removelogo=f={ffmpeg_filter_path(create_gemini_shape_mask(width, height, (x, y, box_w, box_h), preview_dir / 'gemini_preview_mask.png'))}",
                    str(after),
                ],
                check=True, creationflags=0x08000000 if sys.platform == "win32" else 0,
            )
            self.tools_preview_source = str(source)
            self.tools_preview_time_value = shot_time
            self.tools_manual_box = (x, y, box_w, box_h)
            before_pixmap = QPixmap(str(before))
            self.tools_before_preview.set_source(before_pixmap, self.tools_manual_box)
            self.tools_before_preview.setToolTip(
                "Drag a tight box around the entire logo; the app only processes "
                "the sparkle inside the box."
            )
            self._set_tools_preview(self.tools_after_preview, after, "After")
            self.tools_preview_time.setText(
                f"Worst sampled shot {shot_time:.2f}s · multi-frame confidence {confidence:.0%} · "
                f"mask x={x}, y={y}, {box_w}×{box_h}px"
            )
            self.tools_temporal_rerun_button.setEnabled(True)
            self.tools_lama_rerun_button.setEnabled(True)
            original_note = (
                f" Derived output detected; analysis uses original: {source}."
                if source != selected_source else ""
            )
            self.tools_status.setText(
                "Analysis complete. The red box is locked from 12-frame median voting; "
                "adjust it only if it does not tightly cover the logo."
                + original_note
            )
        except Exception as exc:
            QMessageBox.critical(self, "Could Not Analyze Video", str(exc))

    def on_tools_mask_changed(self, box: tuple[int, int, int, int]) -> None:
        try:
            source = Path(self.tools_preview_source)
            if not source.is_file():
                return
            width, height = media_video_size(str(source))
            x, y, box_w, box_h = box
            x = max(0, min(width - 2, x // 2 * 2))
            y = max(0, min(height - 2, y // 2 * 2))
            box_w = max(8, min(width - x, box_w // 2 * 2))
            box_h = max(8, min(height - y, box_h // 2 * 2))
            selection = (x, y, box_w, box_h)
            before = config_dir() / "tools_preview" / "gemini_before.png"
            # A hand-drawn mask is authoritative. Do not run detection again:
            # bright edges inside the selection can otherwise pull the box away
            # from the logo the user already marked correctly.
            self.tools_manual_box = selection
            self.tools_temporal_rerun_button.setEnabled(True)
            self.tools_lama_rerun_button.setEnabled(True)
            x, y, box_w, box_h = self.tools_manual_box
            self.tools_before_preview.set_source(
                QPixmap(str(before)), self.tools_manual_box
            )
            after = config_dir() / "tools_preview" / "gemini_after.png"
            mask_path = create_gemini_shape_mask(
                width, height, self.tools_manual_box,
                config_dir() / "tools_preview" / "gemini_preview_mask.png",
            )
            subprocess.run(
                [
                    ffmpeg_executable(), "-y", "-hide_banner", "-loglevel", "error",
                    "-ss", f"{self.tools_preview_time_value:.3f}", "-i", str(source),
                    "-frames:v", "1",
                    "-vf", f"removelogo=f={ffmpeg_filter_path(mask_path)}",
                    str(after),
                ],
                check=True, creationflags=0x08000000 if sys.platform == "win32" else 0,
            )
            self._set_tools_preview(self.tools_after_preview, after, "After")
            self.tools_preview_time.setText(
                f"Manual mask locked · x={x}, y={y}, {box_w}×{box_h}px"
            )
            self.tools_status.setText(
                "Mask applied. Choose Run Stable Clean or LaMa with the current mask."
            )
        except Exception as exc:
            self.tools_status.setText(f"Could not apply the mask: {exc}")

    @staticmethod
    def _set_tools_preview(label: QLabel, path: Path, title: str) -> None:
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            label.setText(title)
            return
        label.setPixmap(pixmap.scaled(
            label.size(), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))
        label.setToolTip(f"{title}: {path}")

    def on_tools_progress(self, percent: int, message: str) -> None:
        self.tools_progress.setValue(percent)
        self.tools_status_message = message
        self.update_tools_elapsed_status()

    def update_tools_elapsed_status(self) -> None:
        if self.tools_started_at is None:
            self.tools_status.setText(self.tools_status_message)
            return
        elapsed = max(0, time.monotonic() - self.tools_started_at)
        elapsed_text = time.strftime("%H:%M:%S", time.gmtime(elapsed))
        self.tools_status.setText(
            f"{self.tools_status_message} · Elapsed time: {elapsed_text}"
        )

    def on_tools_completed(
        self, mask_output: str, alpha_output: str, temporal_output: str,
        lama_output: str, quality: dict,
    ) -> None:
        self.tools_mask_output = mask_output
        self.tools_alpha_output = alpha_output
        self.tools_temporal_output = temporal_output
        self.tools_lama_output = lama_output
        self.tools_elapsed_timer.stop()
        evaluated = str(quality.get("evaluated", "premium"))
        preferred = {
            "premium": temporal_output,
            "stable": temporal_output,
            "temporal": temporal_output,
            "lama": lama_output,
        }.get(evaluated, temporal_output)
        preview_source = next(
            (
                path for path in (preferred, temporal_output, lama_output, alpha_output, mask_output)
                if Path(path).is_file()
            ),
            "",
        )
        worst_time = float(quality.get("worst_time", self.tools_preview_time_value))
        if worst_time > 0:
            self.tools_preview_time_value = worst_time
        try:
            preview_dir = config_dir() / "tools_preview"
            before_preview = preview_dir / "gemini_worst_before.png"
            official_preview = preview_dir / "gemini_best_after.png"
            subprocess.run(
                [
                    ffmpeg_executable(), "-y", "-hide_banner", "-loglevel", "error",
                    "-ss", f"{self.tools_preview_time_value:.3f}",
                    "-i", self.tools_preview_source,
                    "-frames:v", "1", str(before_preview),
                ],
                check=True, creationflags=0x08000000 if sys.platform == "win32" else 0,
            )
            subprocess.run(
                [
                    ffmpeg_executable(), "-y", "-hide_banner", "-loglevel", "error",
                    "-ss", f"{self.tools_preview_time_value:.3f}", "-i", preview_source,
                    "-frames:v", "1", str(official_preview),
                ],
                check=True, creationflags=0x08000000 if sys.platform == "win32" else 0,
            )
            self.tools_before_preview.set_source(
                QPixmap(str(before_preview)), self.tools_manual_box
            )
            self._set_tools_preview(
                self.tools_after_preview, official_preview, "After · Best available"
            )
        except Exception:
            pass
        self.tools_progress.setValue(100)
        premium_safe = (
            evaluated == "premium" and bool(quality.get("safe", False))
            and Path(alpha_output).is_file()
        )
        recommended = {
            "stable": "Stable Clean",
            "temporal": "Stable Clean",
            "lama": "LaMa Fallback",
        }.get(evaluated, "Stable Clean")
        if evaluated == "stable":
            self.tools_status_message = (
                "Completed · Stable Clean from the original video. "
                "LaMa anchors were propagated bidirectionally inside each scene. "
                "Recommended output: Stable Clean."
            )
        elif evaluated == "temporal":
            self.tools_status_message = (
                "Completed · Stable Clean from the original video. "
                "The logo uses a +10px rectangular mask and balanced scene batches. "
                "Inspect this output carefully."
            )
        elif evaluated == "lama":
            self.tools_status_message = (
                "Completed · LaMa frame fallback. Check motion carefully because "
                "frame-by-frame inpainting can flicker. Recommended output: LaMa Fallback."
            )
        else:
            self.tools_status_message = (
                f"Completed · {evaluated.title()} QA: "
                f"bright {float(quality.get('bright', 1.0)):.0%}, "
                f"dark {float(quality.get('dark', 1.0)):.0%}, "
                f"clipped {float(quality.get('clipped', 1.0)):.0%}. "
                f"Recommended output: {recommended}."
            )
        self.update_tools_elapsed_status()
        self.tools_analyze_button.setEnabled(True)
        for button, path in (
            (self.tools_view_temporal_button, temporal_output),
            (self.tools_use_temporal_button, temporal_output),
            (self.tools_view_lama_button, lama_output),
            (self.tools_use_lama_button, lama_output),
        ):
            button.setEnabled(Path(path).is_file())
        self.tools_temporal_rerun_button.setEnabled(bool(self.tools_manual_box))
        self.tools_lama_rerun_button.setEnabled(bool(self.tools_manual_box))

    def on_tools_failed(self, details: str) -> None:
        self.tools_elapsed_timer.stop()
        self.tools_analyze_button.setEnabled(True)
        self.tools_temporal_rerun_button.setEnabled(bool(self.tools_manual_box))
        self.tools_lama_rerun_button.setEnabled(bool(self.tools_manual_box))
        self.tools_status_message = "Logo removal failed."
        self.update_tools_elapsed_status()
        QMessageBox.critical(self, "Logo Removal Failed", details[-5000:])

    @staticmethod
    def _open_tools_video(path_text: str) -> None:
        path = Path(path_text)
        if path.is_file():
            os.startfile(path)

    def view_temporal_video(self) -> None:
        self._open_tools_video(self.tools_temporal_output)

    def view_lama_video(self) -> None:
        self._open_tools_video(self.tools_lama_output)

    def _use_tools_video(self, path_text: str, method: str) -> None:
        path = Path(path_text)
        if not path.is_file():
            QMessageBox.warning(self, "Select Video", "The result video no longer exists.")
            return
        self.tools_trailer_path.setText(str(path))
        self.watermark_trailer_video.setText(str(path))
        self.persist_settings("watermark")
        self.tools_status.setText(
            f"Selected {method} and updated the trailer path in the Watermark tab: {path}"
        )

    def use_temporal_video(self) -> None:
        self._use_tools_video(self.tools_temporal_output, "Stable Clean")

    def use_lama_video(self) -> None:
        self._use_tools_video(self.tools_lama_output, "LaMa AI")

    def rerun_temporal(self) -> None:
        try:
            source = self._tools_source()
            if not self.tools_manual_box:
                raise ValueError("Draw a tight mask on the preview first.")
            temporal_output = self._tools_output(source, "stable")
            alpha_output = Path(self.tools_alpha_output)
            if (
                not alpha_output.is_file()
                or gemini_original_source(alpha_output) != source
            ):
                alpha_output = self._tools_output(source, "premium")
            self.tools_worker = GeminiLogoWorker(
                str(source), self.tools_mask_output, str(alpha_output),
                str(temporal_output), self.tools_lama_output,
                self.tools_logo_size.value(), self.tools_logo_margin.value(),
                self.tools_manual_box, mode="stable",
            )
            self.tools_thread = QThread()
            self.tools_worker.moveToThread(self.tools_thread)
            self.tools_thread.started.connect(self.tools_worker.run)
            self.tools_worker.progress.connect(self.on_tools_progress)
            self.tools_worker.completed.connect(self.on_tools_completed)
            self.tools_worker.failed.connect(self.on_tools_failed)
            self.tools_worker.completed.connect(self.tools_thread.quit)
            self.tools_worker.failed.connect(self.tools_thread.quit)
            self.tools_analyze_button.setEnabled(False)
            self.tools_temporal_rerun_button.setEnabled(False)
            self.tools_lama_rerun_button.setEnabled(False)
            self.tools_progress.setValue(0)
            self.tools_started_at = time.monotonic()
            self.tools_status_message = (
                "Running Stable Clean from the original with LaMa anchors and bidirectional flow..."
            )
            self.tools_elapsed_timer.start()
            self.update_tools_elapsed_status()
            self.tools_thread.start()
        except Exception as exc:
            QMessageBox.critical(self, "Cannot run Stable Clean", str(exc))

    def rerun_lama(self) -> None:
        try:
            source = self._tools_source()
            if not self.tools_manual_box:
                raise ValueError("Draw an accurate mask on the preview first.")
            lama_output = self._tools_output(source, "lama")
            self.tools_worker = GeminiLogoWorker(
                str(source), self.tools_mask_output, self.tools_alpha_output,
                self.tools_temporal_output, str(lama_output), self.tools_logo_size.value(),
                self.tools_logo_margin.value(), self.tools_manual_box,
                mode="lama",
            )
            self.tools_thread = QThread()
            self.tools_worker.moveToThread(self.tools_thread)
            self.tools_thread.started.connect(self.tools_worker.run)
            self.tools_worker.progress.connect(self.on_tools_progress)
            self.tools_worker.completed.connect(self.on_tools_completed)
            self.tools_worker.failed.connect(self.on_tools_failed)
            self.tools_worker.completed.connect(self.tools_thread.quit)
            self.tools_worker.failed.connect(self.tools_thread.quit)
            self.tools_analyze_button.setEnabled(False)
            self.tools_lama_rerun_button.setEnabled(False)
            self.tools_progress.setValue(80)
            self.tools_started_at = time.monotonic()
            self.tools_status_message = (
                "Rendering LaMa AI from the original video with the current mask..."
            )
            self.tools_elapsed_timer.start()
            self.update_tools_elapsed_status()
            self.tools_thread.start()
        except Exception as exc:
            QMessageBox.critical(self, "Could Not Rerun LaMa", str(exc))

    def automation_stage_card(self, key: str, title: str, subtitle: str) -> QGroupBox:
        card = QGroupBox()
        card.setObjectName(f"automationStage_{key}")
        card.setStyleSheet(
            f"""
            QGroupBox#automationStage_{key} {{
                background: #111927;
                border: 1px solid #2d4058;
                border-radius: 14px;
                margin-top: 0;
                padding: 14px;
            }}
            QGroupBox#automationStage_{key}:hover {{
                border-color: #39d8ff;
                background: #132033;
            }}
            """
        )
        checkbox = QCheckBox("Bật")
        checkbox.setChecked(True)
        checkbox.setObjectName(f"automation_{key}_enabled")
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 22px; font-weight: 800; color: #f4fbff;")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setWordWrap(True)
        subtitle_label.setStyleSheet("color: #9fb3c9;")
        state_label = QLabel("SẼ XỬ LÝ")
        state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        state_label.setStyleSheet(
            "background: #123b4a; color: #39d8ff; border-radius: 10px; "
            "padding: 5px 10px; font-weight: 800;"
        )

        def update_state(checked: bool) -> None:
            state_label.setText("SẼ XỬ LÝ" if checked else "BỎ QUA")
            state_label.setStyleSheet(
                "background: #123b4a; color: #39d8ff; border-radius: 10px; "
                "padding: 5px 10px; font-weight: 800;"
                if checked
                else
                "background: #33202a; color: #ff9fbd; border-radius: 10px; "
                "padding: 5px 10px; font-weight: 800;"
            )

        checkbox.toggled.connect(update_state)
        layout = QVBoxLayout(card)
        top = QHBoxLayout()
        top.addWidget(title_label, 1)
        top.addWidget(state_label)
        layout.addLayout(top)
        layout.addWidget(subtitle_label)
        layout.addWidget(checkbox)
        self.automation_stage_checks[key] = checkbox
        return card

    def update_automation_channel_only_mode(self, checked: bool) -> None:
        if checked:
            self.automation_saved_stage_states = {
                key: checkbox.isChecked()
                for key, checkbox in self.automation_stage_checks.items()
            }
            forced = {
                "voice_clone": False,
                "video_effect": False,
                "caption": False,
                "watermark": True,
            }
            for key, checkbox in self.automation_stage_checks.items():
                checkbox.setChecked(forced[key])
                checkbox.setEnabled(False)
            self.automation_status.setText(
                "Channel-only: Video input là base; chỉ overlay PNG Channel Name, "
                "không render lại base."
            )
        else:
            saved = getattr(self, "automation_saved_stage_states", {})
            for key, checkbox in self.automation_stage_checks.items():
                checkbox.setEnabled(True)
                if key in saved:
                    checkbox.setChecked(saved[key])

    def build_automation_tab(self) -> QWidget:
        self.automation_table = AutomationTableWidget(0, 9)
        self.automation_table.setHorizontalHeaderLabels(
            [
                "Script (.txt/.str/.srt)", "Images folder", "Audio folder", "Video input",
                "Trailer video", "Channel names", "Output folder", "Processing group",
                "Group name",
            ]
        )
        automation_header = self.automation_table.horizontalHeader()
        automation_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        automation_header.setStretchLastSection(False)
        automation_header.setMinimumSectionSize(90)
        self.automation_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        for column, width in enumerate((190, 180, 180, 220, 190, 230, 220, 260, 150)):
            self.automation_table.setColumnWidth(column, width)
        self.automation_table.files_dropped.connect(self.on_automation_files_dropped)
        self.automation_table.rows_reordered.connect(self.refresh_automation_channel_combos)
        self.automation_table.itemChanged.connect(self.on_automation_item_changed)
        self.automation_table.itemSelectionChanged.connect(
            self.sync_selected_automation_processing_group
        )
        self.automation_output_dir = QLineEdit()
        self.automation_output_dir.setPlaceholderText("Thư mục chứa từng bước và video cuối")
        self.automation_channel = QPlainTextEdit()
        self.automation_channel.setPlaceholderText("Mỗi dòng là một Channel Name. Watermark sẽ xuất nhiều video, mỗi tên một file.")
        self.automation_channel.setMaximumHeight(86)
        saved_channel_catalog = self.settings.get(
            "watermark_automation_channel_catalog", "[]"
        )
        try:
            saved_channel_names = json.loads(saved_channel_catalog)
            if not isinstance(saved_channel_names, list):
                saved_channel_names = []
        except (json.JSONDecodeError, TypeError):
            saved_channel_names = [
                line.strip() for line in str(saved_channel_catalog).splitlines()
                if line.strip()
            ]
        self.automation_channel.setPlainText(
            "\n".join(str(name).strip() for name in saved_channel_names if str(name).strip())
        )
        self.automation_logo = QLineEdit()
        self.automation_logo.setPlaceholderText("Logo dùng chung (không bắt buộc)")
        self.automation_warning = QLineEdit(self.watermark_warning_image.text())
        self.automation_subscribe = QLineEdit(self.watermark_subscribe_video.text())
        self.automation_voice_engine = QComboBox()
        self.automation_voice_engine.addItem("Voice Clone (Original)", "original")
        self.automation_voice_engine.addItem("Voice Clone v3", "v3")
        saved_voice_engine = str(
            self.settings.get("automation_voice_engine", "original")
        )
        saved_engine_index = self.automation_voice_engine.findData(saved_voice_engine)
        self.automation_voice_engine.setCurrentIndex(max(0, saved_engine_index))
        self.automation_voice_engine.setToolTip(
            "Original dùng cấu hình tab Voice Clone. Voice Clone v3 dùng voice và "
            "toàn bộ tham số đang chọn trong tab Voice Clone v3."
        )
        self.automation_voice_engine.currentIndexChanged.connect(
            lambda _index: self.persist_settings("watermark")
        )
        self.automation_channel_only = QCheckBox(
            "Đã có base file — chỉ overlay PNG Channel Name"
        )
        self.automation_channel_only.setToolTip(
            "Dùng Video input làm base hoàn chỉnh; bỏ qua Voice Clone, Video Effect, "
            "Caption, trailer, warning và subscribe. Không render lại base."
        )
        self.automation_progress = QProgressBar()
        self.automation_status = QLabel(
            "Sẵn sàng. Pipeline dùng các thông số hiện có của Voice Clone, Video Effect, Caption và Watermark."
        )
        self.automation_status.setWordWrap(True)
        self.automation_log = TranslatedLogEdit()
        self.automation_log.setReadOnly(True)
        self.automation_log.setMaximumBlockCount(500)
        self.automation_thread: QThread | None = None
        self.automation_worker: AutomationWorker | None = None
        self.automation_stage_checks: dict[str, QCheckBox] = {}
        self.automation_last_output_dir: str = ""
        self.automation_batch_end_row = 0
        self.automation_run_completed = False
        self.automation_last_completed_output = ""

        shared = QFormLayout()
        shared.addRow(self.automation_channel_only)
        shared.addRow("Voice engine", self.automation_voice_engine)
        warning_source_widget = self.with_browse(
            self.automation_warning, lambda: self.pick_file_for(
                self.automation_warning, "Warning image", "Image (*.png *.jpg *.jpeg *.webp)"
            )
        )
        subscribe_source_widget = self.with_browse(
            self.automation_subscribe, lambda: self.pick_file_for(
                self.automation_subscribe, "Subscribe video", "Video (*.mp4 *.mov *.mkv *.webm)"
            )
        )
        shared.addRow("Warning image", warning_source_widget)
        shared.addRow("Subscribe video", subscribe_source_widget)
        self.automation_channel_only.toggled.connect(
            lambda checked: warning_source_widget.setEnabled(not checked)
        )
        self.automation_channel_only.toggled.connect(
            lambda checked: subscribe_source_widget.setEnabled(not checked)
        )
        shared_group = QGroupBox("Shared sources")
        shared_group.setLayout(shared)

        pipeline_group = QGroupBox("Pipeline xử lý")
        pipeline_group.setStyleSheet(
            "QGroupBox { font-size: 16px; font-weight: 700; color: #39d8ff; }"
        )
        pipeline_layout = QHBoxLayout(pipeline_group)
        pipeline_layout.setSpacing(10)
        stages = [
            ("voice_clone", "Voice Clone", "Đọc file .txt/.str bằng tham số của tab Voice Clone."),
            ("video_effect", "Video Effect", "Dùng thư mục hình + audio để làm effect theo tab Video Effect."),
            ("caption", "Caption", "Tạo hoặc burn phụ đề theo cấu hình Caption."),
            ("watermark", "Watermark", "Thêm tên kênh, logo, warning và subscribe video."),
        ]
        for index, (key, title, subtitle) in enumerate(stages):
            pipeline_layout.addWidget(self.automation_stage_card(key, title, subtitle), 1)
            if index < len(stages) - 1:
                arrow = QLabel(">")
                arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
                arrow.setStyleSheet("font-size: 34px; font-weight: 900; color: #39d8ff;")
                pipeline_layout.addWidget(arrow)
        self.automation_channel_only.toggled.connect(
            self.update_automation_channel_only_mode
        )

        add_button = self.button("Add automation input", self.add_automation_pair)
        self.automation_add_button = add_button
        trailer_button = self.button("Set trailer video", self.set_automation_trailer_video)
        channels_button = self.button("Edit channel names", self.edit_automation_channel_names)
        output_button = self.button("Set output folder", self.set_automation_output_folder)
        save_button = self.button("Save all", self.save_automation_all)
        import_button = self.button("Import", self.import_automation_all)
        remove_button = self.button("Remove selected", self.remove_automation_rows)
        clear_button = self.button("Clear", lambda: self.automation_table.setRowCount(0))
        render_button = self.button("Render / Gen automation", self.start_automation)
        stop_button = self.button("Stop", self.stop_automation)
        open_button = self.button("Open output folder", self.open_automation_output_folder)
        self.automation_render_button = render_button
        self.automation_stop_button = stop_button
        self.automation_open_output_button = open_button
        stop_button.setEnabled(False)

        left = QWidget()
        left.setMinimumWidth(720)
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(pipeline_group)
        left_layout.addWidget(shared_group)
        batch_header = QHBoxLayout()
        batch_header.addWidget(QLabel(
            "Batch inputs (màu hàng phân biệt Processing group)"
        ))
        batch_header.addStretch(1)
        batch_header.addWidget(QLabel("Nhóm của file đang chọn"))
        self.automation_selected_group_combo = QComboBox()
        self.automation_selected_group_combo.addItems(AUTOMATION_PROCESSING_GROUPS)
        self.automation_selected_group_combo.setMinimumWidth(290)
        self.automation_selected_group_combo.setStyleSheet(
            self.automation_group_combo_style(AUTOMATION_PROCESSING_GROUPS[0])
        )
        self.automation_selected_group_combo.currentTextChanged.connect(
            self.apply_group_to_selected_automation_rows
        )
        batch_header.addWidget(self.automation_selected_group_combo)
        batch_header.addWidget(QLabel("Group name"))
        self.automation_selected_batch_group_combo = QComboBox()
        self.automation_selected_batch_group_combo.setEditable(True)
        self.automation_selected_batch_group_combo.addItems(AUTOMATION_BATCH_GROUPS)
        self.automation_selected_batch_group_combo.setMinimumWidth(130)
        self.automation_selected_batch_group_combo.currentTextChanged.connect(
            self.apply_batch_group_to_selected_automation_rows
        )
        batch_header.addWidget(self.automation_selected_batch_group_combo)
        self.automation_group_rows_button = self.button(
            "Group rows", self.group_automation_rows_by_name
        )
        batch_header.addWidget(self.automation_group_rows_button)
        left_layout.addLayout(batch_header)
        left_layout.addWidget(self.automation_table)
        left_layout.addLayout(self.inline_layout(add_button, trailer_button, channels_button, output_button))
        left_layout.addLayout(self.inline_layout(save_button, import_button, remove_button, clear_button))
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setWidget(left)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        left_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        left_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.automation_left_scroll = left_scroll
        right = QWidget()
        right_layout = QVBoxLayout(right)
        log_header = QHBoxLayout()
        log_header.addWidget(QLabel("Automation log"))
        log_header.addStretch(1)
        self.automation_log_expand_button = self.button(
            "<<", self.toggle_automation_log_expanded
        )
        self.automation_log_expand_button.setFixedWidth(42)
        self.automation_log_expand_button.setToolTip(
            "Mở rộng Automation Log sang trái / khôi phục kích thước"
        )
        log_header.addWidget(self.automation_log_expand_button)
        right_layout.addLayout(log_header)
        right_layout.addWidget(self.automation_log)
        right_layout.addWidget(self.automation_progress)
        right_layout.addWidget(self.automation_status)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_scroll)
        splitter.addWidget(right)
        splitter.setChildrenCollapsible(False)
        splitter.setSizes([1190, 190])
        self.automation_splitter = splitter
        self.automation_log_expanded = False
        self.automation_splitter_normal_sizes = [1190, 190]
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(splitter)
        layout.addLayout(self.inline_layout(render_button, stop_button, open_button))
        return tab

    def toggle_automation_log_expanded(self) -> None:
        sizes = self.automation_splitter.sizes()
        total = max(1, sum(sizes))
        if not self.automation_log_expanded:
            self.automation_splitter_normal_sizes = sizes
            # Expanded layout uses a 1:2.5 left/log ratio. The left side remains
            # usable through its horizontal scrollbar.
            target_right = min(max(1, total - 160), round(total * 2.5 / 3.5))
            self.automation_splitter.setSizes([max(1, total - target_right), target_right])
            self.automation_log_expand_button.setText(">>")
            self.automation_log_expanded = True
        else:
            self.automation_splitter.setSizes(self.automation_splitter_normal_sizes)
            self.automation_log_expand_button.setText("<<")
            self.automation_log_expanded = False

    def pick_folder_for(self, edit: QLineEdit, title: str) -> None:
        path = QFileDialog.getExistingDirectory(self, title, edit.text().strip())
        if path:
            edit.setText(path)

    def pick_file_for(self, edit: QLineEdit, title: str, file_filter: str) -> None:
        path, _ = QFileDialog.getOpenFileName(self, title, edit.text().strip(), file_filter)
        if path:
            edit.setText(path)

    def ensure_automation_row(self, row: int) -> int:
        row = max(0, row)
        while row >= self.automation_table.rowCount():
            self.automation_table.insertRow(self.automation_table.rowCount())
        return row

    def set_automation_cell(self, row: int, column: int, value: str) -> None:
        row = self.ensure_automation_row(row)
        self.automation_table.setItem(row, column, QTableWidgetItem(value))

    def on_automation_item_changed(self, item: QTableWidgetItem) -> None:
        if not self.automation_worker or item.column() not in {4, 5}:
            return
        if item.column() == 4:
            self.automation_worker.update_job_trailer(item.row(), item.text())
            self.automation_log.appendPlainText(
                f"Đã cập nhật Trailer live cho dòng {item.row() + 1}: "
                f"{item.text().strip() or '(bỏ trống)'}"
            )
        else:
            self.automation_worker.update_job_channels(item.row(), item.text())
            names = [line.strip() for line in item.text().splitlines() if line.strip()]
            self.automation_log.appendPlainText(
                f"Đã cập nhật Channel Name live cho dòng {item.row() + 1}: "
                + (", ".join(names) if names else "(không chọn kênh)")
            )

    def automation_channel_names(self) -> list[str]:
        names = [
            line.strip()
            for line in self.automation_channel.toPlainText().splitlines()
            if line.strip()
        ]
        return list(dict.fromkeys(names))

    def set_automation_channel_combo(self, row: int, selected_text: str = "") -> None:
        selected = [line.strip() for line in selected_text.splitlines() if line.strip()]
        channels = self.automation_channel_names()
        if not channels and selected:
            channels = list(dict.fromkeys(selected))
        if not selected and channels:
            selected = channels
        combo = ChannelMultiSelectCombo(channels, selected)

        def update_item(values: list[str], target_row: int = row) -> None:
            if target_row >= self.automation_table.rowCount():
                return
            item = self.automation_table.item(target_row, 5)
            if item is None:
                item = QTableWidgetItem()
                self.automation_table.setItem(target_row, 5, item)
            item.setText("\n".join(values))

        combo.selection_changed.connect(update_item)
        update_item(combo.selected_channels())
        self.automation_table.setCellWidget(row, 5, combo)

    def refresh_automation_channel_combos(self) -> None:
        for row in range(self.automation_table.rowCount()):
            item = self.automation_table.item(row, 5)
            self.set_automation_channel_combo(row, item.text() if item else "")
            group_item = self.automation_table.item(row, 7)
            self.set_automation_processing_group_combo(
                row, group_item.text() if group_item else ""
            )
            batch_group_item = self.automation_table.item(row, 8)
            self.set_automation_batch_group_combo(
                row, batch_group_item.text() if batch_group_item else ""
            )

    def set_automation_processing_group_combo(
        self, row: int, selected_group: str = ""
    ) -> None:
        selected_group = (
            selected_group
            if selected_group in AUTOMATION_PROCESSING_GROUPS
            else AUTOMATION_PROCESSING_GROUPS[0]
        )
        combo = QComboBox()
        combo.addItems(AUTOMATION_PROCESSING_GROUPS)
        combo.setCurrentText(selected_group)
        combo.setStyleSheet(self.automation_group_combo_style(selected_group))

        def update_item(value: str, target_row: int = row) -> None:
            if target_row >= self.automation_table.rowCount():
                return
            item = self.automation_table.item(target_row, 7)
            if item is None:
                item = QTableWidgetItem()
                self.automation_table.setItem(target_row, 7, item)
            item.setText(value)
            combo.setStyleSheet(self.automation_group_combo_style(value))
            self.apply_automation_row_group_color(target_row, value)

        combo.currentTextChanged.connect(update_item)
        update_item(selected_group)
        self.automation_table.setCellWidget(row, 7, combo)

    def set_automation_batch_group_combo(
        self, row: int, batch_group: str = ""
    ) -> None:
        batch_group = AUTOMATION_BATCH_GROUP_ALIASES.get(
            batch_group.strip(), batch_group.strip()
        )
        batch_group = batch_group.strip() or AUTOMATION_BATCH_GROUPS[0]
        combo = QComboBox()
        combo.setEditable(True)
        combo.addItems(AUTOMATION_BATCH_GROUPS)
        if combo.findText(batch_group) < 0:
            combo.addItem(batch_group)
        combo.setCurrentText(batch_group)

        def update_item(value: str, target_row: int = row) -> None:
            value = value.strip() or AUTOMATION_BATCH_GROUPS[0]
            if target_row >= self.automation_table.rowCount():
                return
            item = self.automation_table.item(target_row, 8)
            if item is None:
                item = QTableWidgetItem()
                self.automation_table.setItem(target_row, 8, item)
            item.setText(value)

        combo.currentTextChanged.connect(update_item)
        update_item(batch_group)
        self.automation_table.setCellWidget(row, 8, combo)

    @staticmethod
    def automation_group_color(group: str) -> QColor:
        return {
            AUTOMATION_GROUP_CAPTION_WATERMARK: QColor("#123A46"),
            AUTOMATION_GROUP_VIDEO_EFFECT_CAPTION_WATERMARK: QColor("#49351A"),
            AUTOMATION_GROUP_FULL_PIPELINE: QColor("#382750"),
            AUTOMATION_GROUP_WATERMARK_ONLY: QColor("#173D2C"),
        }.get(group, QColor("#202A38"))

    def automation_group_combo_style(self, group: str) -> str:
        color = self.automation_group_color(group).name()
        return (
            f"QComboBox {{ background: {color}; color: #F4FBFF; "
            "font-weight: 700; border: 1px solid #55708F; padding: 3px; }}"
        )

    def apply_automation_row_group_color(self, row: int, group: str) -> None:
        color = self.automation_group_color(group)
        for column in range(self.automation_table.columnCount()):
            item = self.automation_table.item(row, column)
            if item is not None:
                item.setBackground(color)

    def selected_automation_rows(self) -> list[int]:
        return sorted({
            index.row() for index in self.automation_table.selectedIndexes()
        })

    def sync_selected_automation_processing_group(self) -> None:
        if not hasattr(self, "automation_selected_group_combo"):
            return
        rows = self.selected_automation_rows()
        if not rows:
            return
        item = self.automation_table.item(rows[0], 7)
        group = item.text() if item else AUTOMATION_PROCESSING_GROUPS[0]
        self.automation_selected_group_combo.blockSignals(True)
        self.automation_selected_group_combo.setCurrentText(group)
        self.automation_selected_group_combo.setStyleSheet(
            self.automation_group_combo_style(group)
        )
        self.automation_selected_group_combo.blockSignals(False)
        batch_item = self.automation_table.item(rows[0], 8)
        batch_group = (
            batch_item.text().strip()
            if batch_item and batch_item.text().strip()
            else AUTOMATION_BATCH_GROUPS[0]
        )
        self.automation_selected_batch_group_combo.blockSignals(True)
        if self.automation_selected_batch_group_combo.findText(batch_group) < 0:
            self.automation_selected_batch_group_combo.addItem(batch_group)
        self.automation_selected_batch_group_combo.setCurrentText(batch_group)
        self.automation_selected_batch_group_combo.blockSignals(False)

    def apply_group_to_selected_automation_rows(self, group: str) -> None:
        rows = self.selected_automation_rows()
        if not rows:
            return
        for row in rows:
            combo = self.automation_table.cellWidget(row, 7)
            if isinstance(combo, QComboBox):
                combo.setCurrentText(group)
            else:
                self.set_automation_processing_group_combo(row, group)
        self.automation_selected_group_combo.setStyleSheet(
            self.automation_group_combo_style(group)
        )

    def apply_batch_group_to_selected_automation_rows(self, batch_group: str) -> None:
        batch_group = batch_group.strip()
        if not batch_group:
            return
        for row in self.selected_automation_rows():
            combo = self.automation_table.cellWidget(row, 8)
            if isinstance(combo, QComboBox):
                if combo.findText(batch_group) < 0:
                    combo.addItem(batch_group)
                combo.setCurrentText(batch_group)
            else:
                self.set_automation_batch_group_combo(row, batch_group)

    def group_automation_rows_by_name(self) -> None:
        if self.automation_thread and self.automation_thread.isRunning():
            QMessageBox.information(
                self, "Group rows", "Wait for Automation to finish before reordering."
            )
            return
        rows = self.automation_rows_data()
        predefined_order = {
            name: index for index, name in enumerate(AUTOMATION_BATCH_GROUPS)
        }
        rows.sort(
            key=lambda values: (
                predefined_order.get(
                    values[8] if len(values) > 8 else AUTOMATION_BATCH_GROUPS[0],
                    len(predefined_order),
                ),
                (values[8] if len(values) > 8 else "").lower(),
            )
        )
        self.automation_table.setRowCount(0)
        for values in rows:
            row = self.automation_table.rowCount()
            self.automation_table.insertRow(row)
            padded = list(values) + [""] * (self.automation_table.columnCount() - len(values))
            for column, value in enumerate(padded[: self.automation_table.columnCount()]):
                self.automation_table.setItem(row, column, QTableWidgetItem(value))
        self.refresh_automation_channel_combos()
        self.automation_status.setText("Files were arranged consecutively by Group name.")

    @staticmethod
    def automation_media_count(folder: str, extensions: set[str]) -> int:
        path = Path(folder)
        if not path.is_dir():
            return 0
        try:
            return sum(
                1 for child in path.iterdir()
                if child.is_file() and child.suffix.lower() in extensions
            )
        except OSError:
            return 0

    def warn_automation_media_mismatch(
        self, images: str, audios: str, row: int | None = None
    ) -> bool:
        if not images.strip() or not audios.strip():
            return False
        image_count = self.automation_media_count(images, VIDEO_IMAGE_EXTS)
        audio_count = self.automation_media_count(audios, VIDEO_AUDIO_EXTS)
        if image_count == audio_count:
            return False
        row_text = f" ở dòng {row + 1}" if row is not None else ""
        QMessageBox.warning(
            self,
            "Số lượng ảnh và audio không khớp",
            f"Số lượng ảnh và audio{row_text} không bằng nhau.\n\n"
            f"Ảnh: {image_count} file\n"
            f"Audio: {audio_count} file\n\n"
            "Hãy kiểm tra lại hai thư mục trước khi Render.",
        )
        return True

    def automation_drop_column_for_path(self, path: Path, target_column: int) -> int:
        if target_column in {0, 1, 2, 3, 4, 5, 6}:
            return target_column
        suffix = path.suffix.lower()
        if suffix in {".txt", ".str", ".srt"}:
            return 0
        if path.is_dir():
            try:
                files = [child for child in path.iterdir() if child.is_file()]
            except OSError:
                files = []
            if any(child.suffix.lower() in VIDEO_IMAGE_EXTS for child in files):
                return 1
            if any(child.suffix.lower() in VIDEO_AUDIO_EXTS for child in files):
                return 2
            return 1
        if suffix in VIDEO_AUDIO_EXTS:
            return 2
        if suffix in {".mp4", ".mov", ".mkv", ".avi", ".webm"}:
            return 3
        return 3

    def on_automation_files_dropped(self, paths: list[str], row: int, column: int) -> None:
        if not paths:
            return
        current_row = row if row >= 0 else self.automation_table.rowCount()
        touched_rows: set[int] = set()
        for index, text in enumerate(paths):
            path = Path(text)
            target_row = current_row + index
            touched_rows.add(target_row)
            target_column = self.automation_drop_column_for_path(path, column)
            if column == 4 and path.suffix.lower() in {".mp4", ".mov", ".mkv", ".avi", ".webm"}:
                target_column = 4
            if target_column == 2 and path.is_file() and path.suffix.lower() in VIDEO_AUDIO_EXTS:
                text = str(path.parent)
            self.set_automation_cell(target_row, target_column, text)
            if target_column != 5 and not self.automation_table.item(target_row, 5):
                self.automation_table.setItem(
                    target_row, 5, QTableWidgetItem(self.automation_channel.toPlainText().strip())
                )
        for target_row in sorted(touched_rows):
            channel_item = self.automation_table.item(target_row, 5)
            self.set_automation_channel_combo(
                target_row, channel_item.text() if channel_item else ""
            )
            group_item = self.automation_table.item(target_row, 7)
            self.set_automation_processing_group_combo(
                target_row, group_item.text() if group_item else ""
            )
            batch_group_item = self.automation_table.item(target_row, 8)
            self.set_automation_batch_group_combo(
                target_row, batch_group_item.text() if batch_group_item else ""
            )
            images_item = self.automation_table.item(target_row, 1)
            audios_item = self.automation_table.item(target_row, 2)
            self.warn_automation_media_mismatch(
                images_item.text() if images_item else "",
                audios_item.text() if audios_item else "",
                target_row,
            )
        self.automation_status.setText(f"Đã nhận {len(paths)} item kéo thả vào danh sách Automation.")

    def add_automation_pair(self) -> None:
        processing_group, accepted = QInputDialog.getItem(
            self,
            "Chọn nhóm xử lý",
            "Video này sẽ chạy theo flow:",
            list(AUTOMATION_PROCESSING_GROUPS),
            0,
            False,
        )
        if not accepted:
            return
        batch_group, group_accepted = QInputDialog.getItem(
            self,
            "Select group name",
            "Place this file in:",
            list(AUTOMATION_BATCH_GROUPS),
            0,
            True,
        )
        if not group_accepted:
            return
        batch_group = batch_group.strip() or AUTOMATION_BATCH_GROUPS[0]
        voice_on = processing_group == AUTOMATION_GROUP_FULL_PIPELINE
        effect_on = processing_group in {
            AUTOMATION_GROUP_VIDEO_EFFECT_CAPTION_WATERMARK,
            AUTOMATION_GROUP_FULL_PIPELINE,
        }
        caption_on = processing_group != AUTOMATION_GROUP_WATERMARK_ONLY
        watermark_on = True
        channel_only_input = (
            self.automation_channel_only.isChecked()
            or processing_group == AUTOMATION_GROUP_WATERMARK_ONLY
        )
        if channel_only_input:
            voice_on = False
            effect_on = False
            caption_on = False
            watermark_on = True
        needs_video = not effect_on and (caption_on or watermark_on)
        script = images = audios = video = trailer = output = ""
        if voice_on:
            script, _ = QFileDialog.getOpenFileName(
                self, "Voice Clone script", "", "Script (*.txt *.str *.srt);;Text/SubRip (*.txt *.str *.srt);;All files (*)"
            )
            if not script:
                return
        if effect_on:
            images = QFileDialog.getExistingDirectory(self, "Images folder")
            if not images:
                return
            if not voice_on:
                audios = QFileDialog.getExistingDirectory(self, "Audio folder")
                if not audios:
                    return
                if self.warn_automation_media_mismatch(images, audios):
                    return
        if needs_video:
            video, _ = QFileDialog.getOpenFileName(
                self, "Video input for Caption / Watermark", "", "Video (*.mp4 *.mov *.mkv *.avi *.webm)"
            )
            if not video:
                return
        if watermark_on and not channel_only_input:
            trailer, _ = QFileDialog.getOpenFileName(
                self, "Trailer video for this input (optional)", "", "Video (*.mp4 *.mov *.mkv *.avi *.webm)"
            )
        output = QFileDialog.getExistingDirectory(self, "Output folder for this input")
        if not output:
            return
        row = self.automation_table.rowCount()
        self.automation_table.insertRow(row)
        values = [
            script, images, audios, video, trailer,
            self.automation_channel.toPlainText().strip(), output, processing_group,
            batch_group,
        ]
        for column, value in enumerate(values):
            self.automation_table.setItem(row, column, QTableWidgetItem(value))
        self.set_automation_channel_combo(row, values[5])
        self.set_automation_processing_group_combo(row, values[7])
        self.set_automation_batch_group_combo(row, values[8])

    def remove_automation_rows(self) -> None:
        for row in sorted({index.row() for index in self.automation_table.selectedIndexes()}, reverse=True):
            self.automation_table.removeRow(row)

    def selected_automation_row(self) -> int | None:
        rows = sorted({index.row() for index in self.automation_table.selectedIndexes()})
        return rows[0] if rows else None

    def set_automation_trailer_video(self) -> None:
        row = self.selected_automation_row()
        if row is None:
            QMessageBox.information(self, "Trailer video", "Chọn một dòng input trước.")
            return
        current = self.automation_table.item(row, 4).text() if self.automation_table.item(row, 4) else ""
        path, _ = QFileDialog.getOpenFileName(
            self, "Trailer video for this input", current, "Video (*.mp4 *.mov *.mkv *.avi *.webm)"
        )
        if path:
            self.automation_table.setItem(row, 4, QTableWidgetItem(path))

    def set_automation_output_folder(self) -> None:
        row = self.selected_automation_row()
        if row is None:
            QMessageBox.information(self, "Output folder", "Chọn một dòng input trước.")
            return
        current = self.automation_table.item(row, 6).text() if self.automation_table.item(row, 6) else ""
        path = QFileDialog.getExistingDirectory(self, "Output folder for this input", current)
        if path:
            self.automation_table.setItem(row, 6, QTableWidgetItem(path))

    def edit_automation_channel_names(self) -> None:
        text, ok = QInputDialog.getMultiLineText(
            self,
            "Danh sách Channel Names",
            "Nhập danh sách kênh dùng chung, mỗi dòng một tên.\n"
            "Sau đó tick các kênh cần render tại từng dòng input:",
            self.automation_channel.toPlainText(),
        )
        if ok:
            self.automation_channel.setPlainText(text.strip())
            self.refresh_automation_channel_combos()
            self.persist_settings("watermark")

    def automation_rows_data(self) -> list[list[str]]:
        return [
            [
                self.automation_table.item(row, column).text()
                if self.automation_table.item(row, column) else ""
                for column in range(self.automation_table.columnCount())
            ]
            for row in range(self.automation_table.rowCount())
        ]

    def save_automation_all(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save Automation inputs", "", "JSON (*.json)")
        if not path:
            return
        data = {
            "version": 1,
            "channel_catalog": self.automation_channel_names(),
            "columns": [
                self.automation_table.horizontalHeaderItem(column).text()
                for column in range(self.automation_table.columnCount())
            ],
            "rows": self.automation_rows_data(),
            "shared": {
                "warning_image": self.automation_warning.text().strip(),
                "subscribe_video": self.automation_subscribe.text().strip(),
                "channel_only": self.automation_channel_only.isChecked(),
                "voice_engine": str(
                    self.automation_voice_engine.currentData() or "original"
                ),
            },
            "stages": {
                key: checkbox.isChecked()
                for key, checkbox in self.automation_stage_checks.items()
            },
        }
        Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        self.automation_status.setText(f"Saved Automation inputs: {path}")

    def import_automation_all(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import Automation inputs", "", "JSON (*.json)")
        if not path:
            return
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        rows = data.get("rows", [])
        catalog = [
            str(name).strip()
            for name in data.get("channel_catalog", [])
            if str(name).strip()
        ]
        if not catalog:
            catalog = list(dict.fromkeys(
                channel.strip()
                for values in rows
                if len(values) > 5
                for channel in str(values[5]).splitlines()
                if channel.strip()
            ))
        self.automation_channel.setPlainText("\n".join(catalog))
        self.automation_table.setRowCount(0)
        for values in rows:
            row = self.automation_table.rowCount()
            self.automation_table.insertRow(row)
            for column, value in enumerate(list(values)[: self.automation_table.columnCount()]):
                self.automation_table.setItem(row, column, QTableWidgetItem(str(value)))
        shared = data.get("shared", {})
        self.automation_warning.setText(str(shared.get("warning_image", self.automation_warning.text())))
        self.automation_subscribe.setText(str(shared.get("subscribe_video", self.automation_subscribe.text())))
        imported_voice_engine = str(shared.get("voice_engine", "original"))
        imported_engine_index = self.automation_voice_engine.findData(imported_voice_engine)
        self.automation_voice_engine.setCurrentIndex(max(0, imported_engine_index))
        for key, checked in data.get("stages", {}).items():
            if key in self.automation_stage_checks:
                self.automation_stage_checks[key].setChecked(bool(checked))
        self.automation_channel_only.setChecked(bool(shared.get("channel_only", False)))
        self.refresh_automation_channel_combos()
        self.persist_settings("watermark")
        self.automation_status.setText(f"Imported Automation inputs: {path}")

    def start_automation(
        self, rows_to_render: list[int] | bool | None = None, automatic: bool = False
    ) -> None:
        try:
            # QPushButton.clicked may pass its checked state as the first argument.
            if isinstance(rows_to_render, bool):
                rows_to_render = None
            if self.automation_thread and self.automation_thread.isRunning():
                raise RuntimeError("Automation đang chạy.")
            selected_rows = (
                list(rows_to_render)
                if rows_to_render is not None
                else list(range(self.automation_table.rowCount()))
            )
            self.automation_batch_end_row = self.automation_table.rowCount()
            self.automation_run_completed = False
            stage_config = {
                key: checkbox.isChecked()
                for key, checkbox in self.automation_stage_checks.items()
            }
            channel_only = self.automation_channel_only.isChecked()
            if channel_only:
                stage_config.update({
                    "voice_clone": False,
                    "video_effect": False,
                    "caption": False,
                    "watermark": True,
                    "channel_only": True,
                })
            jobs = []
            for row in selected_rows:
                if row < 0 or row >= self.automation_table.rowCount():
                    continue
                values = [
                    self.automation_table.item(row, column).text().strip()
                    if self.automation_table.item(row, column) else ""
                    for column in range(9)
                ]
                (
                    script, images, audios, video, trailer,
                    channel_names, output, processing_group, batch_group,
                ) = values
                if not any(values):
                    continue
                if processing_group == AUTOMATION_GROUP_VIDEO_EFFECT_CAPTION_WATERMARK:
                    row_stages = {
                        "voice_clone": False, "video_effect": True,
                        "caption": True, "watermark": True,
                    }
                elif processing_group == AUTOMATION_GROUP_FULL_PIPELINE:
                    row_stages = {
                        "voice_clone": True, "video_effect": True,
                        "caption": True, "watermark": True,
                    }
                elif processing_group == AUTOMATION_GROUP_WATERMARK_ONLY:
                    row_stages = {
                        "voice_clone": False, "video_effect": False,
                        "caption": False, "watermark": True,
                        "channel_only": True,
                    }
                else:
                    processing_group = AUTOMATION_GROUP_CAPTION_WATERMARK
                    row_stages = {
                        "voice_clone": False, "video_effect": False,
                        "caption": True, "watermark": True,
                    }
                if channel_only:
                    row_stages = dict(stage_config)
                if row_stages.get("voice_clone", True):
                    if not script or not Path(script).is_file():
                        raise ValueError(f"Dòng {row + 1}: Voice Clone đang bật nên cần file script .txt/.str.")
                if row_stages.get("video_effect", True):
                    if not images or not Path(images).is_dir():
                        raise ValueError(f"Dòng {row + 1}: Video Effect đang bật nên cần Images folder.")
                    if not row_stages.get("voice_clone", True) and (not audios or not Path(audios).is_dir()):
                        raise ValueError(f"Dòng {row + 1}: Voice Clone tắt nên Video Effect cần Audio folder.")
                needs_video = (
                    not row_stages.get("video_effect", True)
                    and (row_stages.get("caption", True) or row_stages.get("watermark", True))
                )
                if needs_video:
                    if not video or not Path(video).is_file():
                        raise ValueError(f"Dòng {row + 1}: cần Video input vì Video Effect đang tắt nhưng bước sau cần video.")
                if not output:
                    raise ValueError(f"Dòng {row + 1}: cần Output folder riêng.")
                jobs.append({
                    "script": script,
                    "images": images,
                    "audios": audios,
                    "video": video,
                    "trailer": trailer,
                    "channels": channel_names,
                    "output": output,
                    "logo": "",
                    "_table_row": row,
                    "processing_group": processing_group,
                    "batch_group": AUTOMATION_BATCH_GROUP_ALIASES.get(
                        batch_group.strip(), batch_group.strip()
                    ) or AUTOMATION_BATCH_GROUPS[0],
                    "stages": row_stages,
                })
            if not jobs:
                raise ValueError("Hãy thêm ít nhất một input Automation.")
            if any(not job["stages"].get("channel_only", False) for job in jobs):
                for optional in (self.automation_warning.text(), self.automation_subscribe.text()):
                    if optional.strip() and not Path(optional.strip()).is_file():
                        raise ValueError(f"Source dùng chung không tồn tại: {optional}")
            voice_engine = str(
                self.automation_voice_engine.currentData() or "original"
            )
            if voice_engine == "v3":
                profile_name = str(
                    self.chatterbox_v3_tab.profile.currentData() or ""
                )
                voice_engine_label = "Voice Clone v3"
            else:
                profile_name = str(self.voice_profile.currentData() or "")
                voice_engine_label = "Voice Clone (Original)"
            if any(job["stages"].get("voice_clone", False) for job in jobs) and not profile_name:
                raise ValueError(
                    f"{voice_engine_label} đang bật: hãy chọn voice profile trong tab tương ứng."
                )
            voice_config = {
                "engine": voice_engine,
                "profile": self.store.load(profile_name) if profile_name else {},
                "model_name": self.model_name.text().strip() or DEFAULT_MODEL,
                "steps": self.steps.value(),
                "fit_timeline": self.fit_timeline.isChecked(),
                "output_format": self.output_format.currentText(),
                "device_mode": self.compute_device.currentData(),
                "cooldown_seconds": self.cooldown_seconds.value(),
                "reload_every": self.reload_every.value(),
                "normalize_audio": self.normalize_audio.isChecked(),
                "language": self.language.currentData(),
                "speaking_style": self.speaking_style.currentText().strip() if self.use_speaking_style.isChecked() else "",
                "auto_style": self.use_speaking_style.isChecked() and self.style_mode.currentData() == "auto",
                "exaggeration": self.chatterbox_v3_tab.exaggeration.value(),
                "cfg_weight": self.chatterbox_v3_tab.cfg_weight.value(),
                "temperature": self.chatterbox_v3_tab.temperature.value(),
                "repetition_penalty": self.chatterbox_v3_tab.repetition.value(),
                "min_p": self.chatterbox_v3_tab.min_p.value(),
                "top_p": self.chatterbox_v3_tab.top_p.value(),
                "auto_qa": self.chatterbox_v3_tab.auto_qa.isChecked(),
                "qa_retries": self.chatterbox_v3_tab.qa_retries.value(),
                "asr_workers": self.chatterbox_v3_tab.asr_workers.value(),
            }
            if voice_engine == "v3":
                voice_config.update({
                    "language": str(self.chatterbox_v3_tab.language.currentData()),
                    "device_mode": str(self.chatterbox_v3_tab.device.currentData()),
                    "output_format": self.chatterbox_v3_tab.output_format.currentText(),
                    "normalize_audio": self.chatterbox_v3_tab.normalize_audio.isChecked(),
                })
            video_config = {
                "width": self.video_effect_width.value(), "height": self.video_effect_height.value(),
                "fps": self.video_effect_fps.value(), "crf": self.video_effect_crf.value(),
                # Automation is throughput-oriented: always prefer an available hardware encoder.
                "codec": require_video_gpu_codec(),
                "workers": self.video_effect_workers.value(),
                "pattern": self.video_effect_pattern.text().strip() or "pan_lr,pan_ud,zoom_in,zoom_out,combo",
                "random_effects": self.video_effect_random_effects.isChecked(),
                "bounce": self.video_effect_bounce.isChecked(),
                "zoom_scale": self.video_effect_zoom_scale.value(),
                "base_crop": self.video_effect_base_crop.value(),
                "edge_reach": self.video_effect_edge_reach.value(),
                "face_safe": self.video_effect_face_safe.value(),
                "speed": self.video_effect_speed.value(),
                "pre_silence": self.video_effect_pre_silence.value(),
                "min_motion": self.video_effect_min_motion.value(),
                "combo_radius": self.video_effect_combo_radius.value(),
                "combo_offset_x": self.video_effect_combo_offset_x.value(),
                "combo_offset_y": self.video_effect_combo_offset_y.value(),
                "retro_preset": self.video_effect_retro_preset.currentText(),
                "retro_scratches_enabled": self.video_effect_retro_scratches_enabled.isChecked(),
                "retro_scratch": self.video_effect_retro_scratch.value(),
                "retro_dust_enabled": self.video_effect_retro_dust_enabled.isChecked(),
                "retro_dust": self.video_effect_retro_dust.value(),
                "retro_grain_enabled": self.video_effect_retro_grain_enabled.isChecked(),
                "retro_grain": self.video_effect_retro_grain.value(),
                "retro_flicker_enabled": self.video_effect_retro_flicker_enabled.isChecked(),
                "retro_flicker": self.video_effect_retro_flicker.value(),
                "retro_vignette_enabled": self.video_effect_retro_vignette_enabled.isChecked(),
                "retro_vignette": self.video_effect_retro_vignette.value(),
                "retro_color_fade_enabled": self.video_effect_retro_color_fade_enabled.isChecked(),
                "retro_color_fade": self.video_effect_retro_color_fade.value(),
                "retro_scan_lines_enabled": self.video_effect_retro_scan_lines_enabled.isChecked(),
                "retro_scan_lines": self.video_effect_retro_scan_lines.value(),
                "merge_videos": self.video_effect_merge.isChecked(),
            }
            caption_config = self.caption_config()
            watermark_config = self.watermark_config()
            watermark_config["codec"] = require_video_gpu_codec()
            watermark_config["target_width"] = 1920
            watermark_config["target_height"] = 1080
            watermark_config["target_fps"] = 24
            watermark_config["warning"]["image"] = self.automation_warning.text().strip()
            watermark_config["subscribe"]["video"] = self.automation_subscribe.text().strip()
            self.automation_worker = AutomationWorker(
                jobs, Path(jobs[0]["output"]), voice_config, video_config, caption_config, watermark_config, stage_config
            )
            self.automation_thread = QThread()
            self.automation_worker.moveToThread(self.automation_thread)
            self.automation_thread.started.connect(self.automation_worker.run)
            self.automation_thread.finished.connect(self.on_automation_thread_finished)
            self.automation_worker.progress.connect(self.on_automation_progress)
            self.automation_worker.completed.connect(self.on_automation_completed)
            self.automation_worker.failed.connect(self.on_automation_failed)
            self.automation_worker.cancelled.connect(self.on_automation_cancelled)
            for signal in (self.automation_worker.completed, self.automation_worker.failed,
                           self.automation_worker.cancelled):
                signal.connect(self.automation_thread.quit)
            self.automation_render_button.setEnabled(False)
            self.automation_stop_button.setEnabled(True)
            self.automation_progress.setRange(0, len(jobs) * 4)
            self.automation_progress.setValue(0)
            if not automatic:
                self.automation_log.clear()
                self.automation_last_output_dir = ""
            else:
                self.automation_log.appendPlainText(
                    f"Phát hiện {len(jobs)} dòng input mới. Tự động render batch tiếp theo."
                )
            encoder = video_config["codec"]
            self.automation_log.appendPlainText(
                f"Render encoder: {encoder} "
                + ("(GPU ưu tiên)" if encoder != "libx264" else "(CPU fallback: không tìm thấy GPU encoder)")
            )
            self.automation_log.appendPlainText(
                f"Voice engine: {voice_engine_label}"
            )
            pipeline_text = " > ".join(
                f"{name}{'' if stage_config[key] else ' (skip)'}"
                for key, name in (
                    ("voice_clone", "Voice Clone"),
                    ("video_effect", "Video Effect"),
                    ("caption", "Caption"),
                    ("watermark", "Watermark"),
                )
            )
            self.automation_log.appendPlainText(f"Pipeline: {pipeline_text}")
            if channel_only:
                self.automation_log.appendPlainText(
                    "Mode: CHANNEL-ONLY — dùng Video input làm base và chỉ overlay "
                    "PNG Channel Name; bỏ qua base render, caption, trailer, warning, subscribe."
                )
            self.automation_status.setText(
                f"Đang render Channel Name cho {len(jobs)} base file..."
                if channel_only
                else f"Đang chạy {len(jobs)} cặp theo thứ tự 4 bước..."
            )
            self.automation_thread.start()
        except Exception as exc:
            QMessageBox.critical(self, "Cannot start Automation", str(exc))

    def stop_automation(self) -> None:
        if self.automation_worker:
            self.automation_worker.cancel()

    def open_automation_output_folder(self) -> None:
        path = self.automation_last_output_dir
        if not path and self.automation_table.rowCount():
            row = self.automation_table.currentRow()
            if row < 0:
                row = 0
            item = self.automation_table.item(row, 6)
            path = item.text().strip() if item else ""
        if path and Path(path).exists():
            os.startfile(path)
        else:
            QMessageBox.information(
                self, "Open output folder", "Hãy chọn Output folder cho dòng input trước."
            )

    def on_automation_progress(self, current: int, total: int, message: str) -> None:
        self.automation_progress.setRange(0, total)
        self.automation_progress.setValue(current)
        self.automation_status.setText(message)
        self.automation_log.appendPlainText(message)

    def finish_automation_ui(self) -> None:
        self.automation_render_button.setEnabled(True)
        self.automation_stop_button.setEnabled(False)
        self.automation_worker = None

    def on_automation_completed(self, output: str) -> None:
        self.finish_automation_ui()
        self.automation_run_completed = True
        self.automation_last_completed_output = output
        self.automation_progress.setValue(self.automation_progress.maximum())
        output_path = Path(output)
        video_dirs = sorted(
            {path.parent for path in output_path.rglob("*.mp4")},
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        ) if output_path.exists() else []
        self.automation_last_output_dir = str(video_dirs[0] if video_dirs else output_path)
        self.automation_status.setText(f"Automation hoàn tất: {output}")
        self.automation_log.appendPlainText(f"Automation hoàn tất: {output}")

    def on_automation_thread_finished(self) -> None:
        if not self.automation_run_completed:
            return
        self.automation_run_completed = False
        first_new_row = self.automation_batch_end_row
        current_row_count = self.automation_table.rowCount()
        if current_row_count > first_new_row:
            new_rows = list(range(first_new_row, current_row_count))
            self.automation_status.setText(
                f"Phát hiện {len(new_rows)} dòng mới; đang chuyển sang batch tiếp theo..."
            )
            self.start_automation(new_rows, automatic=True)
            return
        output = self.automation_last_completed_output
        QMessageBox.information(
            self, "Automation completed", f"Đã xử lý hết hàng đợi.\nKết quả cuối tại:\n{output}"
        )

    def on_automation_failed(self, details: str) -> None:
        self.finish_automation_ui()
        self.automation_status.setText("Automation failed.")
        self.automation_log.appendPlainText(details)
        QMessageBox.critical(self, "Automation failed", details[-5000:])

    def on_automation_cancelled(self, message: str) -> None:
        self.finish_automation_ui()
        self.automation_status.setText(message)
        self.automation_log.appendPlainText(message)

    def inline_layout(self, *widgets) -> QHBoxLayout:
        layout = QHBoxLayout()
        for widget in widgets:
            layout.addWidget(widget)
        return layout

    def watermark_config(self) -> dict:
        codec = self.watermark_codec.currentText()
        return {
            "inputs": self.watermark_input_paths(),
            "names": [x.strip() for x in self.watermark_names.toPlainText().splitlines() if x.strip()],
            "output_dir": self.watermark_output_dir.text().strip(),
            "trailer": {
                "video": self.watermark_trailer_video.text().strip(),
                "transition": self.watermark_transition_duration.value(),
            },
            "position": self.watermark_position.currentText(),
            "name_start": self.watermark_name_start.value(),
            "padding_x": self.watermark_padding_x.value(), "padding_y": self.watermark_padding_y.value(),
            "style": {"font": self.watermark_font.currentText(), "font_size": self.watermark_font_size.value(),
                      "bold": self.watermark_bold.isChecked(), "italic": self.watermark_italic.isChecked(),
                      "text_color": self.clean_hex(self.watermark_text_color.text(), "#FFFFFF"),
                      "background": self.watermark_background.currentText(),
                      "background_color": self.clean_hex(self.watermark_background_color.text(), "#000000"),
                      "background_opacity": self.watermark_background_opacity.value() / 100},
            "warning": {"image": self.watermark_warning_image.text().strip(),
                        "duration": self.watermark_warning_duration.value(), "fit": self.watermark_warning_fit.currentText()},
            "subscribe": {"video": self.watermark_subscribe_video.text().strip(),
                          "start": self.watermark_subscribe_start.value(), "duration": None,
                          "interval": 0, "count": 3,
                          "position": self.watermark_subscribe_position.currentText(), "scale": self.watermark_subscribe_scale.value(),
                          "chroma_key": self.watermark_chroma_key.isChecked(),
                          "chroma_color": self.clean_hex(self.watermark_chroma_color.text(), "#00FF00"),
                          "similarity": self.watermark_chroma_similarity.value(), "blend": self.watermark_chroma_blend.value()},
            "codec": codec, "crf": self.watermark_crf.value(),
        }

    def connect_watermark_signals(self) -> None:
        for widget in (self.watermark_position, self.watermark_font, self.watermark_background,
                       self.watermark_warning_fit, self.watermark_subscribe_position):
            widget.currentTextChanged.connect(self.update_watermark_preview)
        for widget in (self.watermark_padding_x, self.watermark_padding_y, self.watermark_font_size,
                       self.watermark_background_opacity, self.watermark_subscribe_scale,
                       self.watermark_name_start, self.watermark_transition_duration):
            widget.valueChanged.connect(self.update_watermark_preview)
        for widget in (self.watermark_names,):
            widget.textChanged.connect(self.update_watermark_preview)
        for widget in (self.watermark_bold, self.watermark_italic):
            widget.toggled.connect(self.update_watermark_preview)
        for widget in (self.watermark_text_color, self.watermark_background_color,
                       self.watermark_subscribe_video, self.watermark_trailer_video):
            widget.textChanged.connect(self.update_watermark_preview)

    def update_watermark_preview(self) -> None:
        self.watermark_preview.set_config(self.watermark_config())

    def watermark_input_paths(self) -> list[str]:
        paths = []
        for row in range(self.watermark_input_files.count()):
            item = self.watermark_input_files.item(row)
            path = str(item.data(Qt.ItemDataRole.UserRole) or item.text()).strip()
            if path:
                paths.append(path)
        return paths

    def add_watermark_input_path(self, path: str) -> None:
        normalized = str(Path(path))
        if normalized in self.watermark_input_paths():
            return
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, normalized)
        item.setSizeHint(QSize(0, 32))
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(6, 1, 2, 1)
        row_layout.setSpacing(6)
        path_label = QLabel(normalized)
        path_label.setToolTip(normalized)
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        remove_button = QPushButton("×")
        remove_button.setToolTip("Remove this source video")
        remove_button.setFixedSize(28, 26)
        remove_button.clicked.connect(
            lambda _checked=False, list_item=item: self.remove_watermark_input_item(list_item)
        )
        row_layout.addWidget(path_label, 1)
        row_layout.addWidget(remove_button)
        self.watermark_input_files.addItem(item)
        self.watermark_input_files.setItemWidget(item, row_widget)

    def remove_watermark_input_item(self, item: QListWidgetItem) -> None:
        row = self.watermark_input_files.row(item)
        if row >= 0:
            self.watermark_input_files.takeItem(row)

    def pick_watermark_inputs(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Source videos", "", "Video (*.mp4 *.mov *.mkv *.avi *.webm)")
        for path in paths:
            self.add_watermark_input_path(path)

    def pick_watermark_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Watermark output folder")
        if path:
            self.watermark_output_dir.setText(path)

    def pick_watermark_trailer(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Trailer video", "", "Video (*.mp4 *.mov *.mkv *.avi *.webm)")
        if path:
            self.watermark_trailer_video.setText(path)

    def copy_watermark_trailer_path(self) -> None:
        path = self.watermark_trailer_video.text().strip()
        if not path:
            QMessageBox.information(self, "Copy path", "Choose a trailer video first.")
            return
        QApplication.clipboard().setText(path)
        self.watermark_status.setText("Trailer video path copied to clipboard.")

    def pick_watermark_warning(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Warning image", "", "Image (*.png *.jpg *.jpeg *.webp)")
        if path:
            self.watermark_warning_image.setText(path)

    def pick_watermark_subscribe(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Subscribe overlay video", "", "Video (*.mp4 *.mov *.mkv *.webm)")
        if path:
            self.watermark_subscribe_video.setText(path)
            self.capture_watermark_chroma_frame()

    def capture_watermark_chroma_frame(self) -> None:
        source = self.watermark_subscribe_video.text().strip()
        if not Path(source).is_file():
            QMessageBox.warning(self, "Capture frame", "Choose a subscribe overlay video first.")
            return
        destination = config_dir() / "watermark_chroma_preview.png"
        result = subprocess.run(
            [
                ffmpeg_executable(), "-y", "-ss", "0.10", "-i", source,
                "-frames:v", "1", "-update", "1", str(destination),
            ],
            capture_output=True, text=True,
            creationflags=0x08000000 if sys.platform == "win32" else 0,
        )
        if result.returncode != 0 or not self.watermark_chroma_screenshot.set_source(str(destination)):
            QMessageBox.critical(self, "Cannot capture frame", result.stderr[-3000:])
            return
        try:
            duration = media_duration_seconds(source)
            self.watermark_status.setText(
                f"Subscribe duration detected: {duration:.2f}s. Click the screenshot to pick the chroma color."
            )
        except RuntimeError:
            self.watermark_status.setText("Frame captured. Click the screenshot to pick the chroma color.")

    def pick_watermark_chroma_from_image(self, color: str) -> None:
        self.watermark_chroma_color.setText(color)
        self.watermark_status.setText(f"Chroma key color picked from screenshot: {color}")

    def save_watermark_settings(self) -> None:
        self.persist_settings("watermark")
        self.watermark_status.setText("Watermark settings saved and will auto-load next time.")

    def load_watermark_defaults(self) -> None:
        self.apply_watermark_config({
            "position": DEFAULTS["watermark_position"], "padding_x": int(DEFAULTS["watermark_padding_x"]),
            "padding_y": int(DEFAULTS["watermark_padding_y"]),
            "name_start": float(DEFAULTS["watermark_name_start"]),
            "trailer": {"transition": float(DEFAULTS["watermark_transition_duration"])},
            "style": {"font": DEFAULTS["watermark_font"], "font_size": int(DEFAULTS["watermark_font_size"]),
                      "bold": setting_bool(DEFAULTS, "watermark_bold"),
                      "italic": setting_bool(DEFAULTS, "watermark_italic"),
                      "text_color": DEFAULTS["watermark_text_color"], "background": DEFAULTS["watermark_background"],
                      "background_color": DEFAULTS["watermark_background_color"],
                      "background_opacity": int(DEFAULTS["watermark_background_opacity"]) / 100},
            "warning": {"duration": float(DEFAULTS["watermark_warning_duration"]),
                        "fit": DEFAULTS["watermark_warning_fit"]},
            "subscribe": {"start": float(DEFAULTS["watermark_subscribe_start"]),
                          "interval": float(DEFAULTS["watermark_subscribe_interval"]),
                          "count": int(DEFAULTS["watermark_subscribe_count"]),
                          "position": DEFAULTS["watermark_subscribe_position"],
                          "scale": int(DEFAULTS["watermark_subscribe_scale"]),
                          "chroma_key": setting_bool(DEFAULTS, "watermark_chroma_key"),
                          "chroma_color": DEFAULTS["watermark_chroma_color"],
                          "similarity": float(DEFAULTS["watermark_chroma_similarity"]),
                          "blend": float(DEFAULTS["watermark_chroma_blend"])},
            "codec": DEFAULTS["watermark_codec"], "crf": int(DEFAULTS["watermark_crf"]),
        })
        self.watermark_status.setText("Default style and placement loaded; file paths were kept.")

    def apply_watermark_config(self, config: dict) -> None:
        self.watermark_position.setCurrentText(config.get("position", self.watermark_position.currentText()))
        self.watermark_name_start.setValue(float(config.get("name_start", self.watermark_name_start.value())))
        self.watermark_padding_x.setValue(int(config.get("padding_x", self.watermark_padding_x.value())))
        self.watermark_padding_y.setValue(int(config.get("padding_y", self.watermark_padding_y.value())))
        trailer = config.get("trailer", {})
        if "video" in trailer:
            self.watermark_trailer_video.setText(str(trailer["video"]))
        self.watermark_transition_duration.setValue(
            float(trailer.get("transition", self.watermark_transition_duration.value()))
        )
        style = config.get("style", {})
        self.watermark_font.setCurrentText(style.get("font", self.watermark_font.currentText()))
        self.watermark_font_size.setValue(int(style.get("font_size", self.watermark_font_size.value())))
        self.watermark_bold.setChecked(truthy(style.get("bold", self.watermark_bold.isChecked())))
        self.watermark_italic.setChecked(truthy(style.get("italic", self.watermark_italic.isChecked())))
        self.watermark_text_color.setText(style.get("text_color", self.watermark_text_color.text()))
        background = style.get("background", self.watermark_background.currentText())
        self.watermark_background.setCurrentText("Round" if background == "Rounded" else background)
        self.watermark_background_color.setText(style.get("background_color", self.watermark_background_color.text()))
        self.watermark_background_opacity.setValue(round(float(style.get("background_opacity", .55)) * 100))
        warning = config.get("warning", {})
        if "image" in warning:
            self.watermark_warning_image.setText(str(warning["image"]))
        self.watermark_warning_duration.setValue(float(warning.get("duration", self.watermark_warning_duration.value())))
        self.watermark_warning_fit.setCurrentText(warning.get("fit", self.watermark_warning_fit.currentText()))
        subscribe = config.get("subscribe", {})
        if "video" in subscribe:
            self.watermark_subscribe_video.setText(str(subscribe["video"]))
        self.watermark_subscribe_start.setValue(float(subscribe.get("start", self.watermark_subscribe_start.value())))
        self.watermark_subscribe_interval.setValue(float(subscribe.get("interval", self.watermark_subscribe_interval.value())))
        self.watermark_subscribe_count.setValue(int(subscribe.get("count", self.watermark_subscribe_count.value())))
        self.watermark_subscribe_position.setCurrentText(subscribe.get("position", self.watermark_subscribe_position.currentText()))
        self.watermark_subscribe_scale.setValue(int(subscribe.get("scale", self.watermark_subscribe_scale.value())))
        self.watermark_chroma_key.setChecked(bool(subscribe.get("chroma_key", self.watermark_chroma_key.isChecked())))
        self.watermark_chroma_color.setText(subscribe.get("chroma_color", self.watermark_chroma_color.text()))
        self.watermark_chroma_similarity.setValue(float(subscribe.get("similarity", self.watermark_chroma_similarity.value())))
        self.watermark_chroma_blend.setValue(float(subscribe.get("blend", self.watermark_chroma_blend.value())))
        self.watermark_codec.setCurrentText(config.get("codec", self.watermark_codec.currentText()))
        self.watermark_crf.setValue(int(config.get("crf", self.watermark_crf.value())))
        self.update_watermark_preview()

    def import_watermark_settings(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import Watermark settings", "", "JSON (*.json)")
        if not path:
            return
        try:
            config = json.loads(Path(path).read_text(encoding="utf-8"))
            self.apply_watermark_config(config)
            self.watermark_status.setText(f"Imported settings: {Path(path).name}")
        except Exception as exc:
            QMessageBox.critical(self, "Cannot import settings", str(exc))

    def render_watermark(self) -> None:
        try:
            config = self.watermark_config()
            config["target_width"] = 1920
            config["target_height"] = 1080
            config["target_fps"] = 24
            if not config["inputs"] or not config["names"]:
                raise ValueError("Choose at least one source video and enter at least one channel name.")
            for path in config["inputs"]:
                if not Path(path).is_file():
                    raise ValueError(f"Source video does not exist: {path}")
            for optional in (
                config["trailer"]["video"], config["warning"]["image"], config["subscribe"]["video"]
            ):
                if optional and not Path(optional).is_file():
                    raise ValueError(f"Overlay file does not exist: {optional}")
            output_dir = Path(config["output_dir"] or config_dir() / "watermark_exports")
            output_dir.mkdir(parents=True, exist_ok=True)
            jobs = []
            for source in config["inputs"]:
                source_stem = Path(source).stem
                variants = []
                for name in config["names"]:
                    safe = re.sub(r'[<>:"/\\|?*]+', "_", name).strip(" .") or "channel"
                    variants.append({
                        "name": name,
                        "output": str(output_dir / f"{source_stem}_{safe}.mp4"),
                    })
                if len(variants) > 1:
                    jobs.append({
                        "input": source,
                        "name": variants[0]["name"],
                        "output": variants[0]["output"],
                        "variants": variants,
                    })
                else:
                    variant = variants[0]
                    jobs.append({"input": source, "name": variant["name"], "output": variant["output"]})
            self.persist_settings("watermark")
            self.watermark_worker = WatermarkWorker(jobs, config)
            self.watermark_thread = QThread()
            self.watermark_worker.moveToThread(self.watermark_thread)
            self.watermark_thread.started.connect(self.watermark_worker.run)
            self.watermark_worker.progress.connect(self.on_watermark_progress)
            self.watermark_worker.render_progress.connect(self.on_watermark_render_progress)
            self.watermark_worker.completed.connect(self.on_watermark_completed)
            self.watermark_worker.failed.connect(self.on_watermark_failed)
            self.watermark_worker.cancelled.connect(self.on_watermark_cancelled)
            for signal in (self.watermark_worker.completed, self.watermark_worker.failed, self.watermark_worker.cancelled):
                signal.connect(self.watermark_thread.quit)
            self.watermark_render_button.setEnabled(False)
            self.watermark_stop_button.setEnabled(True)
            self.watermark_progress.setRange(0, 100)
            self.watermark_progress.setValue(0)
            self.watermark_render_started = time.monotonic()
            total_outputs = sum(len(job.get("variants", [])) or 1 for job in jobs)
            self.watermark_status.setText(
                f"Fast multi-output: {len(jobs)} source video(s) → "
                f"{total_outputs} channel output(s), tối đa 3 kênh/process..."
            )
            self.watermark_thread.start()
        except Exception as exc:
            QMessageBox.critical(self, "Cannot render Watermark batch", str(exc))

    def stop_watermark(self) -> None:
        if self.watermark_worker:
            self.watermark_worker.cancel()

    def open_watermark_output_folder(self) -> None:
        path = Path(self.watermark_output_dir.text().strip() or config_dir() / "watermark_exports")
        if path.is_dir():
            os.startfile(path)
        else:
            QMessageBox.warning(self, "Watermark output folder", "The output folder does not exist yet.")

    def on_watermark_progress(self, current: int, total: int, name: str) -> None:
        self.watermark_status.setText(f"{current}/{total}: {name}")

    def on_watermark_render_progress(self, percent: int, message: str) -> None:
        self.watermark_progress.setRange(0, 100)
        self.watermark_progress.setValue(percent)
        self.watermark_status.setText(f"{percent}% | {message}")

    def on_watermark_completed(self, output_dir: str) -> None:
        self.watermark_render_button.setEnabled(True)
        self.watermark_stop_button.setEnabled(False)
        elapsed = time.monotonic() - self.watermark_render_started if self.watermark_render_started else 0
        elapsed_text = time.strftime("%H:%M:%S", time.gmtime(elapsed))
        self.watermark_progress.setValue(100)
        self.watermark_status.setText(
            f"Watermark batch completed in {elapsed_text}: {output_dir}"
        )

    def on_watermark_failed(self, details: str) -> None:
        self.watermark_render_button.setEnabled(True)
        self.watermark_stop_button.setEnabled(False)
        self.watermark_status.setText("Watermark render failed.")
        QMessageBox.critical(self, "Watermark render failed", details[-5000:])

    def on_watermark_cancelled(self, message: str) -> None:
        self.watermark_render_button.setEnabled(True)
        self.watermark_stop_button.setEnabled(False)
        self.watermark_status.setText(message)

    def color_control(self, default: str) -> tuple[QWidget, QLineEdit]:
        line_edit = QLineEdit(default)
        line_edit.setMaxLength(7)
        line_edit.setPlaceholderText("#RRGGBB")
        line_edit.setVisible(False)
        swatch = QPushButton()
        swatch.setFixedHeight(28)
        swatch.setMinimumWidth(72)
        swatch.setCursor(Qt.CursorShape.PointingHandCursor)
        wrapper = QWidget()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)

        def update_swatch(value: str) -> None:
            color_value = self.clean_hex(value, default)
            swatch.setToolTip(f"Current color: {color_value}. Click to change.")
            swatch.setStyleSheet(
                "QPushButton {"
                f"background: {color_value};"
                "border: 1px solid #91a4bd;"
                "border-radius: 5px;"
                "}"
                "QPushButton:hover { border: 2px solid #39d8ff; }"
            )

        line_edit.textChanged.connect(update_swatch)
        update_swatch(default)
        swatch.clicked.connect(lambda: self.pick_caption_color(line_edit))
        layout.addWidget(line_edit)
        layout.addWidget(swatch, 1)
        return wrapper, line_edit

    def install_caption_cuda_runtime(self) -> None:
        missing = missing_caption_cuda_packages()
        if not missing:
            paths = configure_caption_cuda_runtime_paths()
            self.caption_status.setText(
                "CUDA runtime for faster-whisper is already installed. "
                f"Registered {len(paths)} DLL folder(s)."
            )
            return
        answer = QMessageBox.question(
            self,
            "Install CUDA runtime for Caption",
            "Caption GPU transcription needs extra NVIDIA CUDA 12 runtime packages:\n\n"
            + "\n".join(f"- {name}" for name in missing)
            + "\n\nInstall them into this app's .conda-env now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.caption_cuda_fix_button.setEnabled(False)
        self.caption_status.setText("Installing CUDA runtime packages for faster-whisper...")
        QApplication.processEvents()
        command = [sys.executable, "-m", "pip", "install", "--upgrade", *missing]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=1800,
                creationflags=0x08000000 if sys.platform == "win32" else 0,
            )
            if result.returncode != 0:
                details = (result.stderr or result.stdout)[-3000:]
                raise RuntimeError(details)
            paths = configure_caption_cuda_runtime_paths()
            self.caption_status.setText(
                "CUDA runtime installed. Restart the app if GPU still reports missing DLLs. "
                f"Registered {len(paths)} DLL folder(s)."
            )
            QMessageBox.information(
                self,
                "CUDA runtime installed",
                "CUDA runtime packages were installed for Caption GPU transcription.\n\n"
                "If the next render still cannot load CUDA, restart the app once.",
            )
        except Exception as exc:
            self.caption_status.setText(f"CUDA runtime install failed: {self.caption_error_summary(exc)}")
            QMessageBox.critical(self, "CUDA runtime install failed", str(exc)[-4000:])
        finally:
            self.caption_cuda_fix_button.setEnabled(True)

    def make_caption_group_collapsible(self, group: QGroupBox) -> None:
        group.setCheckable(True)
        group.setChecked(True)

        def toggle_group(expanded: bool) -> None:
            layout = group.layout()
            if layout is not None:
                for index in range(layout.count()):
                    item = layout.itemAt(index)
                    if item.widget() is not None:
                        item.widget().setVisible(expanded)
                    elif item.layout() is not None:
                        for child_index in range(item.layout().count()):
                            child = item.layout().itemAt(child_index).widget()
                            if child is not None:
                                child.setVisible(expanded)
            group.setMaximumHeight(16777215 if expanded else 30)

        group.toggled.connect(toggle_group)

    def add_caption_batch_row(
        self, source: str = "", import_file: str = "", output: str = "", primary: bool = False
    ) -> dict:
        row_widget = QWidget()
        row_widget.setStyleSheet("border-bottom: 1px solid #303947; padding-bottom: 4px;")
        row_layout = QVBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 6)
        row_layout.setSpacing(4)

        source_edit = self.caption_video_file if primary else QLineEdit(source)
        import_edit = self.caption_import_file if primary else QLineEdit(import_file)
        output_edit = self.caption_output_dir if primary else QLineEdit(output)
        source_edit.setPlaceholderText("Source video/audio")
        import_edit.setPlaceholderText("Optional SRT/JSON")
        output_edit.setPlaceholderText("Optional output folder")

        def task_line(label: str, edit: QLineEdit, callback) -> QWidget:
            wrapper = QWidget()
            line = QHBoxLayout(wrapper)
            line.setContentsMargins(0, 0, 0, 0)
            label_widget = QLabel(label)
            label_widget.setFixedWidth(48)
            line.addWidget(label_widget)
            line.addWidget(edit, 1)
            line.addWidget(self.button("Browse", callback))
            return wrapper

        row_layout.addWidget(
            task_line("Source", source_edit, lambda: self.pick_caption_video_for(source_edit))
        )
        row_layout.addWidget(
            task_line("Import", import_edit, lambda: self.pick_caption_import_for(import_edit))
        )
        output_line = task_line("Output", output_edit, lambda: self.pick_caption_output_for(output_edit))
        if not primary:
            output_line.layout().addWidget(
                self.button("X", lambda: self.remove_caption_batch_row(row))
            )
        row_layout.addWidget(output_line)

        row = {
            "widget": row_widget,
            "source": source_edit,
            "import": import_edit,
            "output": output_edit,
            "primary": primary,
        }
        self.caption_batch_rows.append(row)
        self.caption_batch_layout.addWidget(row_widget)
        self.update_caption_batch_height()
        return row

    def add_caption_batch_row_clicked(self) -> None:
        self.add_caption_batch_row()

    def remove_caption_batch_row(self, row: dict) -> None:
        if row.get("primary") or row not in self.caption_batch_rows:
            return
        self.caption_batch_rows.remove(row)
        self.caption_batch_layout.removeWidget(row["widget"])
        row["widget"].deleteLater()
        self.update_caption_batch_height()

    def update_caption_batch_height(self) -> None:
        row_count = max(1, len(self.caption_batch_rows))
        self.caption_batch_scroll.setFixedHeight(min(330, row_count * 112 + 8))

    def pick_caption_video_for(self, target: QLineEdit) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select caption source", "",
            "Media files (*.mp4 *.mov *.mkv *.mp3 *.wav *.m4a *.aac);;All files (*.*)",
        )
        if path:
            target.setText(path)

    def pick_caption_import_for(self, target: QLineEdit) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import caption file", "",
            "Caption files (*.srt *.json);;All files (*.*)",
        )
        if path:
            target.setText(path)
            if target is self.caption_import_file:
                self.import_caption_file(Path(path))

    def pick_caption_output_for(self, target: QLineEdit) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select caption output folder")
        if path:
            target.setText(path)

    def build_caption_tab(self) -> QWidget:
        input_form = QFormLayout()
        self.caption_batch_container = QWidget()
        self.caption_batch_layout = QVBoxLayout(self.caption_batch_container)
        self.caption_batch_layout.setContentsMargins(0, 0, 0, 0)
        self.caption_batch_layout.setSpacing(8)
        self.caption_batch_scroll = QScrollArea()
        self.caption_batch_scroll.setWidgetResizable(True)
        self.caption_batch_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.caption_batch_scroll.setWidget(self.caption_batch_container)
        self.caption_batch_scroll.setMaximumHeight(330)
        self.add_caption_batch_row(
            self.caption_video_file.text(),
            self.caption_import_file.text(),
            self.caption_output_dir.text(),
            primary=True,
        )
        input_form.addRow("Tasks", self.caption_batch_scroll)
        input_form.addRow(
            "",
            self.button("+ Add caption task", self.add_caption_batch_row_clicked),
        )
        input_form.addRow(
            "Config",
            self.inline_controls(self.caption_save_config_button, self.caption_load_defaults_button),
        )
        input_group = QGroupBox("Input and Mode")
        input_group.setLayout(input_form)

        engine_form = QFormLayout()
        engine_form.addRow("Caption mode", self.caption_mode)
        engine_form.addRow("Engine", self.caption_engine)
        engine_form.addRow("Render", self.caption_render_engine)
        engine_form.addRow("Device", self.paired_controls(self.caption_device, "Model", self.caption_model))
        engine_form.addRow("Language", self.paired_controls(self.caption_language, "Accuracy", self.caption_accuracy))
        engine_form.addRow(
            "Speed",
            self.paired_controls(self.caption_speed_preset, "GPU batch", self.caption_transcribe_batch),
        )
        engine_form.addRow("Workers", self.paired_controls(self.caption_workers, "CUDA", self.caption_cuda_fix_button))
        engine_form.addRow(
            "Options",
            self.inline_controls(
                self.caption_word_timing, self.caption_vad, self.caption_punctuation, self.caption_diarization
            ),
        )
        engine_group = QGroupBox("Local Recognition")
        engine_group.setLayout(engine_form)

        preset_form = QFormLayout()
        preset_form.addRow("Preset", self.caption_preset)
        preset_form.addRow("Notes", self.caption_preset_note)
        preset_group = QGroupBox("CapCut-style Presets")
        preset_group.setLayout(preset_form)

        typography_form = QFormLayout()
        typography_form.addRow("Font", self.paired_controls(self.caption_font_family, "Size", self.caption_font_size))
        typography_form.addRow(
            "Style",
            self.inline_controls(self.caption_bold, self.caption_italic, self.caption_uppercase, self.caption_two_line),
        )
        typography_form.addRow("Line wrap", self.paired_controls(self.caption_max_words, "Chars", self.caption_max_chars))
        typography_form.addRow("Spacing", self.paired_controls(self.caption_letter_spacing, "Line", self.caption_line_spacing))
        typography_group = QGroupBox("Typography")
        typography_group.setLayout(typography_form)

        color_form = QFormLayout()
        color_form.addRow(
            "Text",
            self.paired_controls(
                self.caption_base_color_widget,
                "Active",
                self.caption_active_color_widget,
            ),
        )
        color_form.addRow(
            "Edges",
            self.paired_controls(
                self.caption_outline_color_widget,
                "Shadow",
                self.caption_shadow_color_widget,
            ),
        )
        color_form.addRow("Inactive dim", self.caption_inactive_dim_widget)
        color_group = QGroupBox("Colors")
        color_group.setLayout(color_form)

        effects_form = QFormLayout()
        effects_form.addRow("Outline width", self.caption_outline_width)
        effects_form.addRow("Effects", self.inline_controls(self.caption_shadow_enable, self.caption_glow_enable))
        effects_form.addRow("Shadow offset", self.paired_controls(self.caption_shadow_x, "Y", self.caption_shadow_y))
        effects_form.addRow("Glow strength", self.caption_glow_strength)
        effects_group = QGroupBox("Outline, Shadow, Glow")
        effects_group.setLayout(effects_form)

        background_form = QFormLayout()
        background_form.addRow("Box mode", self.caption_background_mode)
        background_form.addRow("Color", self.caption_background_color_widget)
        background_form.addRow("Opacity", self.caption_background_opacity_widget)
        background_form.addRow("Padding", self.paired_controls(self.caption_padding_x, "Y", self.caption_padding_y))
        background_form.addRow("Corner radius", self.caption_corner_radius)
        background_group = QGroupBox("Background and Box")
        background_group.setLayout(background_form)

        highlight_form = QFormLayout()
        highlight_form.addRow("Type", self.caption_highlight_type)
        highlight_form.addRow("Transition", self.caption_highlight_transition)
        highlight_form.addRow(
            "Motion",
            self.inline_controls(self.caption_reveal_words, self.caption_fade_words, self.caption_pop_active),
        )
        highlight_form.addRow("Scale active", self.caption_scale_active)
        highlight_group = QGroupBox("Highlight")
        highlight_group.setLayout(highlight_form)

        layout_form = QFormLayout()
        layout_form.addRow("Anchor", self.paired_controls(self.caption_anchor, "Align", self.caption_alignment))
        layout_form.addRow("Margins", self.paired_controls(self.caption_margin_bottom, "X", self.caption_margin_x))
        layout_form.addRow(
            "Auto mode",
            self.inline_controls(self.caption_youtube_auto, self.caption_safe_area),
        )
        layout_group = QGroupBox("Position")
        layout_group.setLayout(layout_form)

        timing_form = QFormLayout()
        timing_form.addRow("Duration", self.paired_controls(self.caption_min_duration, "Max", self.caption_max_duration))
        timing_form.addRow("Grouping", self.caption_word_grouping)
        timing_group = QGroupBox("Timing and Line Breaking")
        timing_group.setLayout(timing_form)

        export_form = QFormLayout()
        export_formats = QWidget()
        export_formats_layout = QHBoxLayout(export_formats)
        export_formats_layout.setContentsMargins(0, 0, 0, 0)
        for widget in (self.caption_export_srt, self.caption_export_vtt, self.caption_export_ass, self.caption_export_json):
            export_formats_layout.addWidget(widget)
        export_form.addRow("Formats", export_formats)
        export_form.addRow("Video", self.inline_controls(self.caption_burn_video))
        export_form.addRow("Filename", self.caption_filename_pattern)
        export_group = QGroupBox("Export")
        export_group.setLayout(export_form)

        for form in (
            input_form, engine_form, preset_form, typography_form, color_form, effects_form,
            background_form, highlight_form, layout_form, timing_form, export_form,
        ):
            self.align_left_form(form)
        self.set_caption_tooltips(
            input_form, engine_form, preset_form, typography_form, color_form, effects_form,
            background_form, highlight_form, layout_form, timing_form, export_form,
        )

        left_panel = QWidget()
        left_panel.setMinimumWidth(560)
        left_panel.setMaximumWidth(600)
        left_layout = QVBoxLayout(left_panel)
        for group in (
            input_group, engine_group, preset_group, typography_group, color_group,
            effects_group, background_group, highlight_group, layout_group, timing_group, export_group,
        ):
            self.make_caption_group_collapsible(group)
            left_layout.addWidget(group)
        left_layout.addStretch()
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setWidget(left_panel)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.addWidget(QLabel("Preview"))
        right_layout.addWidget(self.caption_preview)
        preview_actions = QHBoxLayout()
        preview_actions.addWidget(self.button("Refresh preview", self.update_caption_preview))
        preview_actions.addWidget(self.button("Export config JSON", self.export_caption_config))
        preview_actions.addWidget(self.caption_import_button)
        right_layout.addLayout(preview_actions)
        right_layout.addWidget(QLabel("Normalized caption config"))
        right_layout.addWidget(self.caption_config_preview)
        right_layout.addWidget(self.caption_progress)
        right_layout.addWidget(self.caption_elapsed)
        right_layout.addWidget(self.caption_status)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_scroll)
        splitter.addWidget(right_panel)
        splitter.setSizes([600, 680])
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(splitter)
        action_row = QHBoxLayout()
        action_row.addWidget(self.caption_render_button)
        action_row.addWidget(self.caption_stop_button)
        action_row.addWidget(self.caption_open_output_button)
        layout.addLayout(action_row)
        return tab

    def set_caption_tooltips(self, *forms: QFormLayout) -> None:
        tooltip_map = {
            "Source": "Video/audio gốc dùng để tạo caption hoặc burn subtitle vào MP4.",
            "Import": "Dùng file SRT/JSON có sẵn. SRT làm nguồn caption; JSON của app có thể nạp lại cả style và tham số.",
            "Output": "Thư mục lưu SRT/VTT/ASS/JSON/MP4. Nếu để trống, app dùng data/caption_exports.",
            "Config": "Save config lưu toàn bộ thiết lập Caption hiện tại. Load defaults khôi phục mặc định nhưng giữ nguyên các đường dẫn file.",
            "Caption mode": "Standard phù hợp subtitle thường. Pro Highlight dùng word timing để tô từng từ kiểu CapCut/karaoke.",
            "Engine": "Engine local dùng cho bước nhận diện giọng nói. faster-whisper nhẹ hơn; stable-ts/WhisperX hợp word timing.",
            "Render": "Plain subtitle cho SRT/VTT; ASS karaoke giữ style tốt hơn; Burn-in overlay ghi caption trực tiếp vào video.",
            "Device": "Auto để app tự chọn CPU/GPU. GPU nhanh hơn nhưng cần bộ thư viện CUDA phù hợp.",
            "Language": "Chọn Auto nếu chưa rõ ngôn ngữ; chọn English/Spanish khi biết chắc để nhận diện ổn định hơn.",
            "Options": "Word timing cần cho highlight từng từ. VAD lọc khoảng im lặng. Punctuation thêm dấu câu. Diarization tách người nói.",
            "Preset": "Style dựng sẵn giống CapCut để áp nhanh trước khi tinh chỉnh thủ công.",
            "Font": "Font và size ảnh hưởng trực tiếp độ dễ đọc trên video, nhất là Shorts/Reels.",
            "Style": "Bold/Italic/Uppercase/Two-line giúp kiểm soát kiểu chữ và số dòng hiển thị.",
            "Line wrap": "Giới hạn số từ/ký tự mỗi dòng để caption không quá dài và dễ đọc.",
            "Spacing": "Letter spacing và line spacing giúp chữ thoáng hơn hoặc gọn hơn.",
            "Base": "Màu chữ thường.",
            "Active": "Màu của từ đang được đọc tới khi bật highlight.",
            "Outline": "Viền chữ giúp subtitle nổi rõ trên nền video sáng/tối.",
            "Shadow": "Màu bóng đổ, giúp chữ có chiều sâu và dễ đọc hơn.",
            "Text": "Hai mã màu trên cùng một dòng: màu chữ thường và màu từ đang active.",
            "Edges": "Hai mã màu trên cùng một dòng: màu viền chữ và màu bóng đổ.",
            "Inactive dim": "Kéo trái/phải để giảm độ sáng các từ chưa active.",
            "Outline width": "Độ dày viền chữ. Video nền phức tạp thường cần viền dày hơn.",
            "Effects": "Shadow/glow là hiệu ứng phụ; outline vẫn là phần quan trọng nhất để đọc rõ.",
            "Shadow offset": "Dịch bóng đổ theo X/Y.",
            "Box mode": "None không nền; Line box tạo nền cả dòng; Active word box tạo nền riêng cho từ active.",
            "Opacity": "Kéo trái/phải để chỉnh độ trong suốt nền caption.",
            "Padding": "Khoảng cách chữ tới mép box nền.",
            "Corner radius": "Chỉnh độ bo tròn 4 góc của box/background. Giá trị càng cao thì góc càng tròn.",
            "Type": "None tắt highlight; Active color đổi màu từ active; Active background thêm nền; Progressive sweep mô phỏng karaoke sweep.",
            "Transition": "Cách chuyển highlight giữa các từ. Sweep nên dùng với Pro Highlight và word timing.",
            "Motion": "Reveal/Fade/Pop là hiệu ứng nâng cao cho kiểu caption năng động.",
            "Scale active": "Phóng nhẹ từ đang đọc tới để tạo nhấn mạnh.",
            "Anchor": "Vị trí caption trên khung hình.",
            "Margins": "Khoảng cách caption tới cạnh dưới và hai cạnh bên.",
            "Auto mode": "YouTube Auto Position tự canh Bottom-Center và chừa vùng điều khiển phía dưới khi Preview/Render; các thiết lập style khác được giữ nguyên.",
            "Duration": "Giới hạn thời lượng tối thiểu/tối đa của mỗi caption segment.",
            "Grouping": "Cách gom từ thành dòng caption khi có word-level timing.",
            "Formats": "Chọn loại file cần lưu. SRT/VTT đơn giản; ASS giữ style tốt hơn; JSON giữ dữ liệu nội bộ.",
            "Video": "Burned-in MP4 sẽ dùng ffmpeg để ghi caption trực tiếp vào video.",
            "Filename": "Mẫu tên file output. Hỗ trợ {video_name} và {mode}.",
        }
        for form in forms:
            self.set_form_tooltips(form, tooltip_map)
        self.caption_render_button.setToolTip("Render và lưu các file caption đã chọn vào output folder.")
        self.caption_stop_button.setToolTip("Dừng ffmpeg khi đang burn caption vào MP4.")
        self.caption_open_output_button.setToolTip("Mở nhanh thư mục output caption.")
        self.caption_import_button.setToolTip("Import SRT/JSON hiện có để dùng làm nguồn caption hoặc nạp lại style.")
        self.caption_save_config_button.setToolTip("Lưu toàn bộ cấu hình Caption hiện tại để dùng cho lần mở app sau.")
        self.caption_load_defaults_button.setToolTip("Khôi phục cấu hình Caption mặc định và giữ nguyên Source/Import/Output.")

    def connect_caption_signals(self) -> None:
        self.caption_mode.currentTextChanged.connect(self.update_caption_mode)
        self.caption_preset.currentTextChanged.connect(self.apply_caption_preset)
        widgets = [
            self.caption_engine, self.caption_render_engine, self.caption_device,
            self.caption_language, self.caption_model, self.caption_accuracy,
            self.caption_speed_preset, self.caption_transcribe_batch, self.caption_workers,
            self.caption_font_family, self.caption_font_size, self.caption_bold,
            self.caption_italic, self.caption_uppercase, self.caption_letter_spacing,
            self.caption_line_spacing, self.caption_max_words, self.caption_max_chars,
            self.caption_two_line, self.caption_base_color, self.caption_active_color,
            self.caption_outline_color, self.caption_shadow_color, self.caption_inactive_dim,
            self.caption_outline_width, self.caption_shadow_enable, self.caption_shadow_x,
            self.caption_shadow_y, self.caption_glow_enable, self.caption_glow_strength,
            self.caption_background_mode, self.caption_background_color,
            self.caption_background_opacity, self.caption_padding_x, self.caption_padding_y,
            self.caption_corner_radius, self.caption_highlight_type,
            self.caption_highlight_transition, self.caption_reveal_words,
            self.caption_fade_words, self.caption_pop_active, self.caption_scale_active,
            self.caption_anchor, self.caption_alignment, self.caption_margin_bottom,
            self.caption_margin_x, self.caption_safe_area, self.caption_youtube_auto, self.caption_min_duration,
            self.caption_max_duration, self.caption_word_grouping, self.caption_export_srt,
            self.caption_export_vtt, self.caption_export_ass, self.caption_export_json,
            self.caption_burn_video, self.caption_filename_pattern, self.caption_import_file, self.caption_word_timing,
            self.caption_vad, self.caption_punctuation, self.caption_diarization,
        ]
        for widget in widgets:
            if isinstance(widget, QComboBox):
                widget.currentTextChanged.connect(self.update_caption_preview)
            elif isinstance(widget, (QSpinBox, QDoubleSpinBox, QSlider)):
                widget.valueChanged.connect(self.update_caption_preview)
            elif isinstance(widget, QCheckBox):
                widget.toggled.connect(self.update_caption_preview)
            elif isinstance(widget, QLineEdit):
                widget.textChanged.connect(self.update_caption_preview)

    def pick_caption_color(self, line_edit: QLineEdit) -> None:
        color = QColorDialog.getColor(QColor(line_edit.text()), self, "Pick caption color")
        if color.isValid():
            line_edit.setText(color.name().upper())

    def apply_caption_preset(self, name: str, update_combo: bool = True) -> None:
        preset = CAPTION_STYLE_PRESETS.get(name, CAPTION_STYLE_PRESETS[CAPTION_PRESET_ORDER[0]])
        if update_combo:
            self.caption_preset.setCurrentText(name)
        self.caption_preset_note.setText(preset["note"])
        self.caption_mode.setCurrentText(preset["mode"])
        self.caption_font_family.setCurrentText(preset["font_family"])
        self.caption_font_size.setValue(int(preset["font_size"]))
        self.caption_bold.setChecked(bool(preset["bold"]))
        self.caption_italic.setChecked(bool(preset["italic"]))
        self.caption_uppercase.setChecked(bool(preset["uppercase"]))
        self.caption_base_color.setText(preset["base_color"])
        self.caption_active_color.setText(preset["active_color"])
        self.caption_outline_color.setText(preset["outline_color"])
        self.caption_outline_width.setValue(int(preset["outline_width"]))
        self.caption_shadow_enable.setChecked(bool(preset["shadow"]))
        self.caption_shadow_color.setText(preset["shadow_color"])
        self.caption_background_mode.setCurrentText(preset["background_mode"])
        self.caption_background_color.setText(preset["background_color"])
        self.caption_background_opacity.setValue(int(preset["background_opacity"]))
        self.caption_highlight_type.setCurrentText(preset["highlight_type"])
        self.caption_highlight_transition.setCurrentText(preset["highlight_transition"])
        self.caption_reveal_words.setChecked(bool(preset["reveal_words"]))
        self.caption_scale_active.setValue(int(preset["scale_active_word"]))
        self.caption_anchor.setCurrentText(preset["anchor"])
        self.caption_alignment.setCurrentText(preset["alignment"])
        self.caption_margin_bottom.setValue(int(preset["margin_bottom"]))
        self.update_caption_mode()
        self.update_caption_preview()

    def reset_caption_preset(self) -> None:
        self.apply_caption_preset(self.caption_preset.currentText())

    def save_caption_configuration(self) -> None:
        self.persist_settings("caption")
        self.caption_status.setText("Caption configuration saved.")

    def restore_saved_caption_configuration(self) -> bool:
        saved_json = self.settings.get("caption_config_json", "").strip()
        if not saved_json:
            return False
        try:
            config = json.loads(saved_json)
            if not isinstance(config, dict):
                raise ValueError("Saved Caption config must be a JSON object.")
            self.apply_caption_config_values(config)
            self.caption_status.setText("Saved Caption configuration loaded.")
            return True
        except (TypeError, ValueError, json.JSONDecodeError):
            self.caption_status.setText("Saved Caption configuration was invalid; defaults were loaded.")
            return False

    def load_default_caption_config(self) -> None:
        self.caption_engine.setCurrentText(DEFAULTS["caption_engine"])
        self.caption_device.setCurrentText(DEFAULTS["caption_device"])
        self.caption_language.setCurrentText(DEFAULTS["caption_language"])
        self.caption_model.setCurrentText(DEFAULTS["caption_model"])
        self.caption_accuracy.setCurrentText(DEFAULTS["caption_accuracy"])
        self.caption_speed_preset.setCurrentText(DEFAULTS["caption_speed_preset"])
        self.caption_transcribe_batch.setValue(setting_int(DEFAULTS, "caption_transcribe_batch"))
        self.caption_workers.setValue(setting_int(DEFAULTS, "caption_workers"))
        self.caption_max_words.setValue(6)
        self.caption_max_chars.setValue(36)
        self.caption_two_line.setChecked(True)
        self.caption_export_srt.setChecked(True)
        self.caption_export_vtt.setChecked(False)
        self.caption_export_ass.setChecked(False)
        self.caption_export_json.setChecked(True)
        self.caption_burn_video.setChecked(True)
        self.caption_youtube_auto.setChecked(True)
        self.apply_caption_preset(DEFAULTS["caption_preset"])
        self.caption_status.setText("Default Caption configuration loaded. File paths were kept.")

    def update_caption_mode(self) -> None:
        pro_mode = self.caption_mode.currentText() == "Pro Highlight"
        if pro_mode:
            # Pro Highlight uses faster-whisper word timestamps; stable-ts/WhisperX
            # are listed for future backends but are not connected to this renderer.
            self.caption_engine.setCurrentText("faster-whisper")
            self.caption_render_engine.setCurrentText("ASS karaoke")
            self.caption_word_timing.setChecked(True)
            self.caption_export_ass.setChecked(True)
            self.caption_highlight_type.setEnabled(True)
            self.caption_reveal_words.setEnabled(True)
        else:
            if self.caption_engine.currentText() in {"stable-ts", "WhisperX"}:
                self.caption_engine.setCurrentText("faster-whisper")
            self.caption_render_engine.setCurrentText("Plain subtitle")
            self.caption_word_timing.setChecked(False)
            self.caption_highlight_type.setEnabled(True)
            self.caption_reveal_words.setEnabled(False)
        self.caption_status.setText(
            "Pro Highlight uses faster-whisper word timing for ASS/burn-in."
            if pro_mode
            else "Standard uses faster-whisper for SRT/JSON and burn-in."
        )
        self.update_caption_preview()

    def caption_config(self) -> dict:
        formats = []
        if self.caption_export_srt.isChecked():
            formats.append("srt")
        if self.caption_export_vtt.isChecked():
            formats.append("vtt")
        if self.caption_export_ass.isChecked():
            formats.append("ass")
        if self.caption_export_json.isChecked():
            formats.append("json")
        youtube_auto = self.caption_youtube_auto.isChecked()
        return {
            "mode": self.caption_mode.currentText(),
            "source": {
                "video_file": self.caption_video_file.text().strip(),
                "import_file": self.caption_import_file.text().strip(),
                "output_dir": self.caption_output_dir.text().strip(),
            },
            "transcribe": {
                "engine": self.caption_engine.currentText(),
                "model": self.caption_model.currentText(),
                "language": self.caption_language.currentText(),
                "accuracy": self.caption_accuracy.currentText(),
                "device": self.caption_device.currentText(),
                "speed_preset": self.caption_speed_preset.currentText(),
                "batch_size": self.caption_transcribe_batch.value(),
                "workers": self.caption_workers.value(),
                "word_timing": self.caption_word_timing.isChecked(),
                "vad_filter": self.caption_vad.isChecked(),
                "punctuation": self.caption_punctuation.isChecked(),
                "diarization": self.caption_diarization.isChecked(),
            },
            "style": {
                "preset": self.caption_preset.currentText(),
                "font_family": self.caption_font_family.currentText(),
                "font_size": self.caption_font_size.value(),
                "bold": self.caption_bold.isChecked(),
                "italic": self.caption_italic.isChecked(),
                "uppercase": self.caption_uppercase.isChecked(),
                "letter_spacing": self.caption_letter_spacing.value(),
                "line_spacing": self.caption_line_spacing.value(),
                "base_color": self.clean_hex(self.caption_base_color.text(), "#FFFFFF"),
                "active_color": self.clean_hex(self.caption_active_color.text(), "#FF8A00"),
                "outline_color": self.clean_hex(self.caption_outline_color.text(), "#000000"),
                "outline_width": self.caption_outline_width.value(),
                "shadow": self.caption_shadow_enable.isChecked(),
                "shadow_color": self.clean_hex(self.caption_shadow_color.text(), "#000000"),
                "shadow_offset_x": self.caption_shadow_x.value(),
                "shadow_offset_y": self.caption_shadow_y.value(),
                "inactive_dim": self.caption_inactive_dim.value() / 100,
                "background_mode": self.caption_background_mode.currentText(),
                "background_color": self.clean_hex(self.caption_background_color.text(), "#000000"),
                "background_opacity": self.caption_background_opacity.value() / 100,
                "padding_x": self.caption_padding_x.value(),
                "padding_y": self.caption_padding_y.value(),
                "corner_radius": self.caption_corner_radius.value(),
                "highlight_type": self.caption_highlight_type.currentText(),
                "highlight_transition": self.caption_highlight_transition.currentText(),
                "reveal_words": self.caption_reveal_words.isChecked(),
                "fade_words": self.caption_fade_words.isChecked(),
                "pop_active_word": self.caption_pop_active.isChecked(),
                "scale_active_word": self.caption_scale_active.value(),
            },
            "layout": {
                "anchor": "Bottom" if youtube_auto else self.caption_anchor.currentText(),
                "alignment": "Center" if youtube_auto else self.caption_alignment.currentText(),
                "margin_bottom": 96 if youtube_auto else self.caption_margin_bottom.value(),
                "margin_x": 64 if youtube_auto else self.caption_margin_x.value(),
                "safe_area_preview": self.caption_safe_area.isChecked(),
                "youtube_auto_position": youtube_auto,
                "max_words_per_line": self.caption_max_words.value(),
                "max_chars_per_line": self.caption_max_chars.value(),
                "two_line_mode": self.caption_two_line.isChecked(),
                "word_grouping": self.caption_word_grouping.currentText(),
                "min_caption_duration": self.caption_min_duration.value(),
                "max_caption_duration": self.caption_max_duration.value(),
            },
            "export": {
                "formats": formats,
                "burn_video": self.caption_burn_video.isChecked(),
                "filename_pattern": self.caption_filename_pattern.text().strip(),
            },
        }

    def clean_hex(self, value: str, fallback: str) -> str:
        value = value.strip().upper()
        if re.fullmatch(r"#[0-9A-F]{6}", value):
            return value
        return fallback

    def update_caption_preview(self) -> None:
        if not hasattr(self, "caption_preview"):
            return
        config = self.caption_config()
        self.caption_preview.set_config(config)
        self.caption_config_preview.setPlainText(json.dumps(config, ensure_ascii=False, indent=2))

    def dim_hex_color(self, value: str, dim: float) -> str:
        value = self.clean_hex(value, "#FFFFFF")
        dim = max(0.0, min(1.0, dim))
        red = int(value[1:3], 16)
        green = int(value[3:5], 16)
        blue = int(value[5:7], 16)
        bg = 17
        red = round(bg + (red - bg) * dim)
        green = round(bg + (green - bg) * dim)
        blue = round(bg + (blue - bg) * dim)
        return f"#{red:02X}{green:02X}{blue:02X}"

    def hex_with_alpha(self, value: str, opacity: float) -> str:
        value = self.clean_hex(value, "#000000")
        red = int(value[1:3], 16)
        green = int(value[3:5], 16)
        blue = int(value[5:7], 16)
        return f"rgba({red}, {green}, {blue}, {opacity:.2f})"

    def pick_caption_video_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select caption source",
            "",
            "Media files (*.mp4 *.mov *.mkv *.mp3 *.wav *.m4a *.aac);;All files (*.*)",
        )
        if path:
            self.caption_video_file.setText(path)

    def pick_caption_import_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import caption file",
            "",
            "Caption files (*.srt *.json);;All files (*.*)",
        )
        if path:
            self.caption_import_file.setText(path)
            self.import_caption_file(Path(path))

    def pick_caption_output_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select caption output folder")
        if path:
            self.caption_output_dir.setText(path)

    def caption_output_root(self, create: bool = False) -> Path:
        root_text = self.caption_output_dir.text().strip()
        if root_text:
            root = Path(root_text)
        else:
            source_path = Path(self.caption_video_file.text().strip())
            import_path = Path(self.caption_import_file.text().strip())
            if source_path.is_file():
                base_dir = source_path.parent
            elif import_path.is_file():
                base_dir = import_path.parent
            else:
                base_dir = config_dir()
            base_name = re.sub(r'[<>:"/\\|?*]+', "_", base_dir.name).strip(" .") or "caption"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            root = base_dir / f"{base_name}_caption_exports_{timestamp}"
        if create:
            root.mkdir(parents=True, exist_ok=True)
            if not root_text:
                self.caption_output_dir.setText(str(root))
        return root

    def open_caption_output_folder(self) -> None:
        path = self.caption_output_root(create=True)
        os.startfile(path)

    def import_caption_file(self, path: Path) -> None:
        try:
            if not path.is_file():
                raise ValueError("Caption import file does not exist.")
            if path.suffix.lower() == ".json":
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and {"style", "layout", "export"} & set(data):
                    self.apply_caption_config_values(data)
                    self.caption_status.setText("Imported caption config JSON and updated controls.")
                else:
                    segments = self.caption_segments_from_json(data)
                    self.caption_status.setText(f"Imported JSON timing with {len(segments)} segment(s).")
            elif path.suffix.lower() == ".srt":
                segments = self.parse_srt_text(path.read_text(encoding="utf-8", errors="replace"))
                self.caption_status.setText(f"Imported SRT with {len(segments)} segment(s).")
            else:
                raise ValueError("Use .srt or .json for caption import.")
            self.update_caption_preview()
        except Exception as exc:
            QMessageBox.critical(self, "Cannot import caption", str(exc))

    def apply_caption_config_values(self, config: dict) -> None:
        transcribe = config.get("transcribe", {}) if isinstance(config, dict) else {}
        style = config.get("style", {}) if isinstance(config, dict) else {}
        layout = config.get("layout", {}) if isinstance(config, dict) else {}
        export = config.get("export", {}) if isinstance(config, dict) else {}
        source = config.get("source", {}) if isinstance(config, dict) else {}
        if config.get("mode"):
            self.caption_mode.setCurrentText(str(config["mode"]))
        if "video_file" in source:
            self.caption_video_file.setText(str(source["video_file"]))
        if "import_file" in source:
            self.caption_import_file.setText(str(source["import_file"]))
        if "output_dir" in source:
            self.caption_output_dir.setText(str(source["output_dir"]))
        for key, widget in (
            ("engine", self.caption_engine),
            ("model", self.caption_model),
            ("language", self.caption_language),
            ("accuracy", self.caption_accuracy),
            ("device", self.caption_device),
            ("speed_preset", self.caption_speed_preset),
        ):
            if transcribe.get(key):
                widget.setCurrentText(str(transcribe[key]))
        if transcribe.get("batch_size") is not None:
            try:
                self.caption_transcribe_batch.setValue(int(transcribe["batch_size"]))
            except (TypeError, ValueError):
                self.caption_transcribe_batch.setValue(setting_int(DEFAULTS, "caption_transcribe_batch"))
        if transcribe.get("workers") is not None:
            try:
                self.caption_workers.setValue(int(transcribe["workers"]))
            except (TypeError, ValueError):
                self.caption_workers.setValue(setting_int(DEFAULTS, "caption_workers"))
        for key, widget in (
            ("word_timing", self.caption_word_timing),
            ("vad_filter", self.caption_vad),
            ("punctuation", self.caption_punctuation),
            ("diarization", self.caption_diarization),
        ):
            if key in transcribe:
                widget.setChecked(bool(transcribe[key]))
        for key, widget in (
            ("font_family", self.caption_font_family),
            ("background_mode", self.caption_background_mode),
            ("highlight_type", self.caption_highlight_type),
            ("highlight_transition", self.caption_highlight_transition),
            ("anchor", self.caption_anchor),
            ("alignment", self.caption_alignment),
        ):
            value = style.get(key, layout.get(key))
            if value:
                widget.setCurrentText(str(value))
        for key, widget in (
            ("font_size", self.caption_font_size),
            ("letter_spacing", self.caption_letter_spacing),
            ("outline_width", self.caption_outline_width),
            ("shadow_offset_x", self.caption_shadow_x),
            ("shadow_offset_y", self.caption_shadow_y),
            ("padding_x", self.caption_padding_x),
            ("padding_y", self.caption_padding_y),
            ("corner_radius", self.caption_corner_radius),
            ("scale_active_word", self.caption_scale_active),
            ("margin_bottom", self.caption_margin_bottom),
            ("margin_x", self.caption_margin_x),
            ("max_words_per_line", self.caption_max_words),
            ("max_chars_per_line", self.caption_max_chars),
        ):
            value = style.get(key, layout.get(key))
            if value is not None:
                widget.setValue(int(value))
        for key, widget in (
            ("base_color", self.caption_base_color),
            ("active_color", self.caption_active_color),
            ("outline_color", self.caption_outline_color),
            ("shadow_color", self.caption_shadow_color),
            ("background_color", self.caption_background_color),
        ):
            if style.get(key):
                widget.setText(str(style[key]))
        for key, widget in (
            ("bold", self.caption_bold),
            ("italic", self.caption_italic),
            ("uppercase", self.caption_uppercase),
            ("shadow", self.caption_shadow_enable),
            ("reveal_words", self.caption_reveal_words),
            ("fade_words", self.caption_fade_words),
            ("pop_active_word", self.caption_pop_active),
            ("two_line_mode", self.caption_two_line),
            ("safe_area_preview", self.caption_safe_area),
            ("youtube_auto_position", self.caption_youtube_auto),
        ):
            value = style.get(key, layout.get(key))
            if value is not None:
                widget.setChecked(bool(value))
        if style.get("background_opacity") is not None:
            self.caption_background_opacity.setValue(round(float(style["background_opacity"]) * 100))
        if style.get("inactive_dim") is not None:
            self.caption_inactive_dim.setValue(round(float(style["inactive_dim"]) * 100))
        if style.get("line_spacing") is not None:
            self.caption_line_spacing.setValue(float(style["line_spacing"]))
        if layout.get("min_caption_duration") is not None:
            self.caption_min_duration.setValue(float(layout["min_caption_duration"]))
        if layout.get("max_caption_duration") is not None:
            self.caption_max_duration.setValue(float(layout["max_caption_duration"]))
        if layout.get("word_grouping"):
            self.caption_word_grouping.setCurrentText(str(layout["word_grouping"]))
        if "formats" in export:
            formats = set(export.get("formats", []))
            self.caption_export_srt.setChecked("srt" in formats)
            self.caption_export_vtt.setChecked("vtt" in formats)
            self.caption_export_ass.setChecked("ass" in formats)
            self.caption_export_json.setChecked("json" in formats)
        if export.get("burn_video") is not None:
            self.caption_burn_video.setChecked(bool(export["burn_video"]))
        if "filename_pattern" in export:
            self.caption_filename_pattern.setText(str(export["filename_pattern"]))

    def export_caption_config(self) -> None:
        self.update_caption_preview()
        default_dir = self.caption_output_dir.text().strip() or str(config_dir())
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export caption config",
            str(Path(default_dir) / "caption_config.json"),
            "JSON files (*.json);;All files (*.*)",
        )
        if not path:
            return
        config = self.caption_config()
        Path(path).write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        self.caption_status.setText(f"Caption config exported: {path}")

    def render_caption(self) -> None:
        tasks = [
            row for row in self.caption_batch_rows
            if row["source"].text().strip() or row["import"].text().strip()
        ]
        if not tasks:
            QMessageBox.warning(
                self, "Caption batch", "Add at least one Source video or SRT/JSON import."
            )
            return
        original = (
            self.caption_video_file.text(),
            self.caption_import_file.text(),
            self.caption_output_dir.text(),
        )
        completed = 0
        try:
            for index, task in enumerate(tasks, 1):
                self.caption_video_file.setText(task["source"].text().strip())
                self.caption_import_file.setText(task["import"].text().strip())
                self.caption_output_dir.setText(task["output"].text().strip())
                self.caption_status.setText(f"Caption batch {index}/{len(tasks)}: preparing...")
                if not self._render_caption_single(show_dialog=False):
                    break
                completed += 1
                if self.caption_cancel_requested:
                    break
        finally:
            self.caption_video_file.setText(original[0])
            self.caption_import_file.setText(original[1])
            self.caption_output_dir.setText(original[2])
            self.persist_settings("caption")
            self.update_caption_preview()
        if completed == len(tasks):
            self.caption_status.setText(f"Caption batch completed: {completed}/{len(tasks)} task(s).")
            QMessageBox.information(
                self, "Caption batch completed", f"Completed {completed} caption task(s)."
            )

    def _render_caption_single(self, show_dialog: bool = True) -> bool:
        try:
            if self.caption_process is not None:
                raise RuntimeError("Caption render is already running.")
            self.caption_cancel_requested = False
            self.caption_render_button.setEnabled(False)
            self.caption_progress.setRange(0, 0)
            self.caption_elapsed.setText("Preparing captions...")
            config = self.caption_config()
            output_dir = self.caption_output_root(create=True)
            generated_from_media = not self.caption_import_file.text().strip()
            segments = self.current_caption_segments()
            if not segments:
                raise ValueError("No speech was detected in the source video.")
            segments = self.group_caption_segments(
                segments,
                max_words=config["layout"]["max_words_per_line"],
            )
            if generated_from_media:
                for required_format in ("srt", "json"):
                    if required_format not in config["export"]["formats"]:
                        config["export"]["formats"].append(required_format)
            self.caption_progress.setRange(0, 100)
            self.caption_progress.setValue(35)
            self.caption_elapsed.setText(f"Caption data ready | {len(segments)} segment(s)")
            stem = self.caption_output_stem(config)
            written: list[Path] = []
            caption_data_dir = output_dir / "caption_data"
            caption_data_dir.mkdir(parents=True, exist_ok=True)
            for suffix in (".srt", ".vtt", ".ass"):
                legacy_sidecar = output_dir / f"{stem}{suffix}"
                if legacy_sidecar.is_file():
                    legacy_sidecar.unlink()
            if "json" in config["export"]["formats"]:
                path = caption_data_dir / f"{stem}.json"
                path.write_text(
                    json.dumps({"config": config, "segments": segments}, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                written.append(path)
            if "srt" in config["export"]["formats"]:
                path = caption_data_dir / f"{stem}.srt"
                path.write_text(self.segments_to_srt(segments), encoding="utf-8")
                written.append(path)
            if "vtt" in config["export"]["formats"]:
                path = caption_data_dir / f"{stem}.vtt"
                path.write_text("WEBVTT\n\n" + self.segments_to_vtt_body(segments), encoding="utf-8")
                written.append(path)
            ass_path: Path | None = None
            if "ass" in config["export"]["formats"] or config["export"]["burn_video"]:
                ass_path = caption_data_dir / f"{stem}.ass"
                ass_path.write_text(self.segments_to_ass(segments, config), encoding="utf-8")
                written.append(ass_path)
            if config["export"]["burn_video"]:
                video_path = Path(config["source"]["video_file"])
                if not video_path.is_file():
                    raise ValueError("Burned-in MP4 requires a valid source video.")
                if ass_path is None:
                    raise ValueError("ASS subtitle file was not generated.")
                mp4_path = output_dir / f"{stem}.mp4"
                self.caption_stop_button.setEnabled(True)
                gpu_codec = available_video_gpu_codec()
                codec = gpu_codec or "libx264"
                self.caption_status.setText(
                    f"Burning captions into MP4 with {codec}"
                    + (" (GPU)..." if gpu_codec else " (CPU)...")
                )
                filter_arg = f"subtitles={self.ffmpeg_filter_path(ass_path)}"
                ffmpeg_log = output_dir / f"{stem}.ffmpeg.log"
                speed_preset = config["transcribe"].get("speed_preset", "Fast GPU")
                workers = int(config["transcribe"].get("workers", setting_int(DEFAULTS, "caption_workers")))
                code = self.run_caption_ffmpeg(
                    video_path, ass_path, mp4_path, codec, ffmpeg_log, speed_preset, workers
                )
                if code != 0 and gpu_codec:
                    self.caption_status.setText(
                        f"{gpu_codec} was unavailable at runtime. Retrying with CPU (libx264)..."
                    )
                    code = self.run_caption_ffmpeg(
                        video_path, ass_path, mp4_path, "libx264", ffmpeg_log, speed_preset, workers
                    )
                if code != 0:
                    stderr = ffmpeg_log.read_text(encoding="utf-8", errors="replace")
                    raise RuntimeError("ffmpeg burn-in failed:\n" + stderr[-2500:])
                written.append(mp4_path)
            self.caption_progress.setRange(0, 100)
            self.caption_progress.setValue(100)
            self.caption_elapsed.setText("Completed | 100%")
            self.persist_settings("caption")
            self.caption_status.setText(
                f"Caption render completed. Saved {len(written)} file(s) to {output_dir.name}."
            )
            self.caption_render_button.setEnabled(True)
            if show_dialog:
                QMessageBox.information(self, "Caption render completed", f"Saved to:\n{output_dir}")
            return True
        except Exception as exc:
            self.caption_process = None
            self.caption_transcribe_job = None
            self.caption_stop_button.setEnabled(False)
            self.caption_render_button.setEnabled(True)
            self.caption_progress.setRange(0, 100)
            self.caption_progress.setValue(0)
            if self.caption_cancel_requested:
                self.caption_status.setText("Caption render stopped.")
                self.caption_elapsed.setText("Stopped")
                return False
            self.caption_status.setText("Caption render failed.")
            if show_dialog:
                QMessageBox.critical(self, "Cannot render captions", str(exc))
            else:
                self.caption_status.setText(f"Caption batch stopped: {self.caption_error_summary(exc)}")
            return False

    def run_caption_ffmpeg(
        self,
        video_path: Path,
        ass_path: Path,
        mp4_path: Path,
        codec: str,
        ffmpeg_log: Path,
        speed_preset: str = "Fast GPU",
        workers: int = 4,
    ) -> int:
        self.caption_stop_button.setEnabled(True)
        filter_arg = f"subtitles={self.ffmpeg_filter_path(ass_path)}"
        filter_threads = max(1, min(workers, os.cpu_count() or 1))
        try:
            duration = media_duration_seconds(str(video_path))
        except Exception:
            duration = 0.0
        burn_started_at = time.monotonic()
        self.caption_progress.setRange(0, 100)
        self.caption_progress.setValue(max(self.caption_progress.value(), 65))
        command = [
            ffmpeg_executable(), "-y", "-i", str(video_path),
            "-filter_threads", str(filter_threads), "-vf", filter_arg,
            "-map", "0:v:0", "-map", "0:a?", "-sn",
            "-c:v", codec,
        ]
        if codec in {"h264_nvenc", "hevc_nvenc"}:
            nvenc_profiles = {
                "Fast GPU": ("p1", "23"),
                "Balanced": ("p4", "20"),
                "Quality": ("p6", "18"),
            }
            preset, cq = nvenc_profiles.get(speed_preset, nvenc_profiles["Fast GPU"])
            if codec == "hevc_nvenc" and speed_preset == "Fast GPU":
                cq = "25"
            command.extend(["-preset", preset, "-tune", "hq", "-rc", "vbr", "-cq", cq, "-b:v", "0"])
        elif codec == "libx264":
            cpu_profiles = {
                "Fast GPU": ("veryfast", "23"),
                "Balanced": ("faster", "20"),
                "Quality": ("slow", "18"),
            }
            preset, crf = cpu_profiles.get(speed_preset, cpu_profiles["Fast GPU"])
            command.extend(["-preset", preset, "-crf", crf, "-threads", "0"])
        command.extend(["-c:a", "copy", "-movflags", "+faststart", "-progress", "pipe:1", "-nostats", str(mp4_path)])
        with ffmpeg_log.open("a", encoding="utf-8", errors="replace") as log_handle:
            log_handle.write(f"\n\nTrying video encoder: {codec} | speed preset: {speed_preset}\n")
            self.caption_process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=log_handle,
                text=True,
                bufsize=1,
                creationflags=0x08000000 if sys.platform == "win32" else 0,
            )
            while self.caption_process.poll() is None:
                line = self.caption_process.stdout.readline() if self.caption_process.stdout else ""
                if line:
                    key, _, value = line.strip().partition("=")
                    if key in {"out_time_us", "out_time_ms"} and duration > 0:
                        try:
                            rendered = float(value) / 1_000_000
                        except ValueError:
                            rendered = 0.0
                        percent = min(99, max(65, round(rendered / duration * 100)))
                        elapsed = time.strftime(
                            "%H:%M:%S", time.gmtime(time.monotonic() - burn_started_at)
                        )
                        self.caption_progress.setValue(percent)
                        self.caption_elapsed.setText(
                            f"Burning MP4 with {codec} | {percent}% | elapsed {elapsed}"
                        )
                    elif key == "progress" and value == "end":
                        self.caption_progress.setValue(99)
                        self.caption_elapsed.setText(f"Finalizing MP4 with {codec}...")
                QApplication.processEvents()
                time.sleep(0.05)
            code = self.caption_process.returncode
        self.caption_process = None
        self.caption_stop_button.setEnabled(False)
        return code

    def stop_caption_render(self) -> None:
        self.caption_cancel_requested = True
        if self.caption_transcribe_job is not None:
            if self.caption_transcribe_job.is_alive():
                self.caption_transcribe_job.terminate()
                self.caption_transcribe_job.join(timeout=3)
            self.caption_transcribe_job = None
            self.caption_status.setText("Caption transcription stopped.")
            self.caption_progress.setRange(0, 100)
            self.caption_progress.setValue(0)
            self.caption_stop_button.setEnabled(False)
            return
        if self.caption_process is not None:
            self.caption_process.terminate()
            self.caption_status.setText("Stopping caption render...")
            self.caption_stop_button.setEnabled(False)

    def caption_output_stem(self, config: dict) -> str:
        source = Path(config["source"]["video_file"]).stem or Path(config["source"]["import_file"]).stem or "caption"
        mode = config["mode"].lower().replace(" ", "_")
        pattern = config["export"]["filename_pattern"] or "{video_name}_caption_{mode}"
        stem = pattern.replace("{video_name}", source).replace("{mode}", mode)
        stem = re.sub(r'[<>:"/\\|?*]+', "_", stem).strip(" .")
        return stem or f"{source}_caption_{mode}"

    def current_caption_segments(self) -> list[dict]:
        import_text = self.caption_import_file.text().strip()
        if import_text:
            path = Path(import_text)
            if path.suffix.lower() == ".srt":
                return self.parse_srt_text(path.read_text(encoding="utf-8", errors="replace"))
            if path.suffix.lower() == ".json":
                data = json.loads(path.read_text(encoding="utf-8"))
                return self.caption_segments_from_json(data)
        source_path = Path(self.caption_video_file.text().strip())
        if not source_path.is_file():
            raise ValueError("Choose a source video/audio file or import an SRT/JSON file.")
        return self.transcribe_caption_source(source_path)

    def transcribe_caption_source(self, source_path: Path) -> list[dict]:
        if self.caption_engine.currentText() != "faster-whisper":
            raise ValueError(
                f"{self.caption_engine.currentText()} is not connected yet. "
                "Choose faster-whisper or import an SRT/JSON file."
            )
        requested_device = self.caption_device.currentText()
        devices = ["cpu"] if requested_device == "CPU" else ["cuda", "cpu"]
        language = {"English": "en", "Spanish": "es"}.get(self.caption_language.currentText())
        beam_size = {"Fast": 1, "Balanced": 3, "Best": 5}.get(self.caption_accuracy.currentText(), 3)
        batch_size = self.caption_transcribe_batch.value()
        workers = self.caption_workers.value()
        try:
            duration = media_duration_seconds(str(source_path))
        except Exception:
            duration = 0.0
        transcribe_started_at = time.monotonic()
        self.caption_progress.setRange(0, 100)
        self.caption_progress.setValue(1)
        last_error: Exception | None = None
        for device in devices:
            try:
                self.caption_status.setText(
                    f"Transcribing with faster-whisper on {device.upper()}"
                    + (f" (batch {batch_size}, workers {workers})..." if device == "cuda" else f" (workers {workers})...")
                )
                self.caption_stop_button.setEnabled(True)
                QApplication.processEvents()
                model_name = self.caption_model.currentText()
                vad_filter = self.caption_vad.isChecked()
                word_timestamps = (
                    self.caption_word_timing.isChecked()
                    or self.caption_mode.currentText() == "Pro Highlight"
                    or self.caption_highlight_type.currentText() != "None"
                    or self.caption_background_mode.currentText() == "Active word box"
                )

                context = multiprocessing.get_context("spawn")
                result_queue = context.Queue()
                self.caption_transcribe_job = context.Process(
                    target=caption_transcribe_process,
                    args=(
                        {
                            "source_path": str(source_path),
                            "device": device,
                            "model_name": model_name,
                            "language": language,
                            "beam_size": beam_size,
                            "batch_size": batch_size,
                            "workers": workers,
                            "vad_filter": vad_filter,
                            "word_timestamps": word_timestamps,
                        },
                        result_queue,
                    ),
                    daemon=True,
                )
                self.caption_transcribe_job.start()
                transcribe_job = self.caption_transcribe_job
                last_progress_at = time.monotonic()
                completed_segments = None
                error_details = ""
                while transcribe_job.is_alive():
                    try:
                        while True:
                            message_type, payload = result_queue.get_nowait()
                            last_progress_at = time.monotonic()
                            if message_type == "progress":
                                if isinstance(payload, dict):
                                    count = int(payload.get("count", 0))
                                    end_time = float(payload.get("end", 0.0))
                                else:
                                    count = int(payload)
                                    end_time = 0.0
                                percent = min(99, max(1, round(end_time / duration * 100))) if duration > 0 else 1
                                elapsed = time.strftime(
                                    "%H:%M:%S", time.gmtime(time.monotonic() - transcribe_started_at)
                                )
                                self.caption_progress.setValue(percent)
                                self.caption_elapsed.setText(
                                    f"Transcribing | {percent}% | {count} segment(s) | elapsed {elapsed}"
                                )
                            elif message_type == "completed":
                                completed_segments = payload
                            elif message_type == "error":
                                error_details = str(payload)
                    except queue.Empty:
                        pass
                    if time.monotonic() - last_progress_at > 900:
                        transcribe_job.terminate()
                        transcribe_job.join(timeout=3)
                        raise TimeoutError(
                            "Whisper made no progress for 15 minutes and was stopped. "
                            "Try model small/turbo or reduce the source duration."
                        )
                    QApplication.processEvents()
                    time.sleep(0.05)
                transcribe_job.join(timeout=3)
                self.caption_transcribe_job = None
                try:
                    while True:
                        message_type, payload = result_queue.get_nowait()
                        if message_type == "completed":
                            completed_segments = payload
                        elif message_type == "error":
                            error_details = str(payload)
                except queue.Empty:
                    pass
                self.caption_stop_button.setEnabled(False)
                if error_details:
                    raise RuntimeError(error_details)
                if completed_segments is None:
                    raise RuntimeError("Caption transcription stopped before completion.")
                aligned_segments, timing_scale = align_caption_segments_to_media_duration(
                    list(completed_segments), duration
                )
                if timing_scale < 1.0:
                    drift = max(
                        (float(segment.get("end", 0.0)) for segment in completed_segments),
                        default=duration,
                    ) - duration
                    self.caption_status.setText(
                        f"Corrected accumulated caption drift: {drift:.2f}s."
                    )
                    log_event(
                        "CAPTION | corrected accumulated audio clock drift | "
                        f"drift={drift:.3f}s | decoded/media ratio={1.0 / timing_scale:.6f}"
                    )
                return aligned_segments
            except Exception as exc:
                last_error = exc
                if self.caption_cancel_requested:
                    break
                if device == "cpu":
                    break
                self.caption_status.setText(
                    "CUDA transcription unavailable; retrying on CPU. "
                    + self.caption_error_summary(exc)
                )
                QApplication.processEvents()
        if self.caption_cancel_requested:
            raise RuntimeError("Caption transcription was stopped.")
        raise RuntimeError(f"Caption transcription failed: {self.caption_error_summary(last_error)}")

    def caption_error_summary(self, error: BaseException | None) -> str:
        details = str(error or "").strip()
        if "cublas64_12.dll" in details:
            return (
                "Missing cublas64_12.dll. Install the matching CUDA 12 runtime/cuBLAS, "
                "or keep Device on Auto/CPU."
            )
        if "cudnn" in details.lower():
            return "CUDA/cuDNN runtime is missing or incompatible. Keep Device on Auto/CPU or install matching CUDA libraries."
        lines = [line.strip() for line in details.splitlines() if line.strip()]
        return (lines[-1] if lines else "Unknown error")[:500]

    def caption_segments_from_json(self, data) -> list[dict]:
        if isinstance(data, dict):
            if isinstance(data.get("segments"), list):
                return [self.normalize_caption_segment(segment) for segment in data["segments"]]
            if isinstance(data.get("words"), list):
                words = [self.normalize_caption_word(word) for word in data["words"]]
                text = " ".join(word["text"] for word in words)
                start = words[0]["start"] if words else 0.0
                end = words[-1]["end"] if words else 0.0
                return [{"start": start, "end": end, "text": text, "words": words}]
            if isinstance(data.get("config"), dict) and isinstance(data.get("segments"), list):
                return [self.normalize_caption_segment(segment) for segment in data["segments"]]
        if isinstance(data, list):
            return [self.normalize_caption_segment(segment) for segment in data]
        raise ValueError("JSON must contain segments[] or words[].")

    def normalize_caption_segment(self, segment: dict) -> dict:
        start = float(segment.get("start", 0.0))
        end = float(segment.get("end", start + 1.0))
        text = str(segment.get("text", "")).strip()
        words = [self.normalize_caption_word(word) for word in segment.get("words", []) if isinstance(word, dict)]
        if not text and words:
            text = " ".join(word["text"] for word in words)
        return {"start": start, "end": end, "text": text, "words": words}

    def normalize_caption_word(self, word: dict) -> dict:
        return {
            "text": str(word.get("text", word.get("word", ""))).strip(),
            "start": float(word.get("start", 0.0)),
            "end": float(word.get("end", word.get("start", 0.0))),
        }

    def parse_srt_text(self, text: str) -> list[dict]:
        blocks = re.split(r"\n\s*\n", text.replace("\r\n", "\n").strip())
        segments = []
        pattern = re.compile(
            r"(?P<start>\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(?P<end>\d{2}:\d{2}:\d{2}[,.]\d{3})"
        )
        for block in blocks:
            lines = [line.strip() for line in block.splitlines() if line.strip()]
            if not lines:
                continue
            time_index = next((index for index, line in enumerate(lines) if "-->" in line), -1)
            if time_index < 0:
                continue
            match = pattern.search(lines[time_index])
            if not match:
                continue
            caption_text = " ".join(lines[time_index + 1 :]).strip()
            segments.append(
                {
                    "start": self.parse_caption_timestamp(match.group("start")),
                    "end": self.parse_caption_timestamp(match.group("end")),
                    "text": caption_text,
                    "words": [],
                }
            )
        return segments

    def parse_caption_timestamp(self, value: str) -> float:
        hours, minutes, rest = value.replace(",", ".").split(":")
        seconds = float(rest)
        return int(hours) * 3600 + int(minutes) * 60 + seconds

    def format_srt_timestamp(self, seconds: float) -> str:
        millis = round(max(0.0, seconds) * 1000)
        hours, rem = divmod(millis, 3600000)
        minutes, rem = divmod(rem, 60000)
        secs, ms = divmod(rem, 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"

    def format_ass_timestamp(self, seconds: float) -> str:
        centis = round(max(0.0, seconds) * 100)
        hours, rem = divmod(centis, 360000)
        minutes, rem = divmod(rem, 6000)
        secs, cs = divmod(rem, 100)
        return f"{hours}:{minutes:02d}:{secs:02d}.{cs:02d}"

    def segments_to_srt(self, segments: list[dict]) -> str:
        blocks = []
        for index, segment in enumerate(segments, 1):
            blocks.append(
                f"{index}\n{self.format_srt_timestamp(segment['start'])} --> {self.format_srt_timestamp(segment['end'])}\n{segment['text']}"
            )
        return "\n\n".join(blocks) + "\n"

    def segments_to_vtt_body(self, segments: list[dict]) -> str:
        return self.segments_to_srt(segments).replace(",", ".")

    def segments_to_ass(self, segments: list[dict], config: dict) -> str:
        style = config["style"]
        layout = config["layout"]
        alignment = {"Left": 1, "Center": 2, "Right": 3}.get(layout["alignment"], 2)
        anchor_offset = {"Bottom": 0, "Middle": 3, "Top": 6}.get(layout["anchor"], 0)
        alignment += anchor_offset
        primary = self.ass_color(style["base_color"])
        secondary = self.ass_color(style["active_color"])
        outline = self.ass_color(style["outline_color"])
        back = self.ass_color(style["shadow_color"])
        bold = -1 if style["bold"] else 0
        italic = -1 if style["italic"] else 0
        line_box = style["background_mode"] == "Line box"
        border_style = 3 if line_box else 1
        style_outline = self.ass_color(style["background_color"]) if line_box else outline
        style_outline_width = max(style["padding_x"], style["padding_y"]) if line_box else style["outline_width"]
        header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{style['font_family']},{style['font_size']},{primary},{secondary},{style_outline},{back},{bold},{italic},0,0,100,100,{style['letter_spacing']},0,{border_style},{style_outline_width},2,{alignment},{layout['margin_x']},{layout['margin_x']},{layout['margin_bottom']},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        lines = [header]
        for segment in segments:
            words = self.caption_words_with_timing(segment)
            highlight_type = style["highlight_type"]
            if highlight_type == "None" or not words:
                text = self.ass_escape(segment["text"])
                if style["uppercase"]:
                    text = text.upper()
                lines.append(self.ass_dialogue_line(segment["start"], segment["end"], text))
                continue
            if highlight_type == "Progressive sweep":
                karaoke_parts = []
                for word in words:
                    duration_cs = max(1, round((word["end"] - word["start"]) * 100))
                    text = word["text"].upper() if style["uppercase"] else word["text"]
                    karaoke_parts.append(f"{{\\kf{duration_cs}}}{self.ass_escape(text)}")
                lines.append(
                    self.ass_dialogue_line(
                        segment["start"], segment["end"], " ".join(karaoke_parts)
                    )
                )
                continue
            event_cursor = float(segment["start"])
            segment_end = max(event_cursor + 0.01, float(segment["end"]))
            for active_index, word in enumerate(words):
                rendered_words = []
                for index, item in enumerate(words):
                    text = item["text"].upper() if style["uppercase"] else item["text"]
                    escaped = self.ass_escape(text)
                    if index == active_index:
                        if highlight_type == "Active background" or style["background_mode"] == "Active word box":
                            background = self.ass_override_color(style["background_color"])
                            escaped = (
                                f"{{\\1c{self.ass_override_color(style['active_color'])}"
                                f"\\3c{background}\\bord{max(6, style['padding_y'])}}}"
                                f"{escaped}{{\\r}}"
                            )
                        else:
                            escaped = (
                                f"{{\\1c{self.ass_override_color(style['active_color'])}}}"
                                f"{escaped}{{\\r}}"
                            )
                    rendered_words.append(escaped)
                event_start = max(event_cursor, float(segment["start"]) if active_index == 0 else float(word["start"]))
                event_end = (
                    float(words[active_index + 1]["start"])
                    if active_index + 1 < len(words)
                    else segment_end
                )
                event_end = min(segment_end, max(event_start + 0.01, event_end))
                if event_start >= segment_end:
                    continue
                lines.append(
                    self.ass_dialogue_line(
                        event_start,
                        event_end,
                        " ".join(rendered_words),
                    )
                )
                event_cursor = event_end
        return "".join(lines)

    def caption_words_with_timing(self, segment: dict) -> list[dict]:
        segment_start = float(segment.get("start", 0.0))
        segment_end = max(segment_start + 0.01, float(segment.get("end", segment_start + 0.01)))
        raw_words = sorted(
            (
                word for word in segment.get("words", [])
                if word.get("text")
            ),
            key=lambda word: (float(word.get("start", segment_start)), float(word.get("end", segment_end))),
        )
        if raw_words:
            normalized = []
            cursor = segment_start
            for word in raw_words:
                text = str(word.get("text", "")).strip()
                if not text:
                    continue
                start = max(segment_start, cursor, float(word.get("start", cursor)))
                end = min(segment_end, float(word.get("end", start + 0.05)))
                if end <= start:
                    end = min(segment_end, start + 0.05)
                if end <= start:
                    continue
                normalized.append({"text": text, "start": start, "end": end})
                cursor = end
            if normalized:
                return normalized
        tokens = str(segment.get("text", "")).split()
        if not tokens:
            return []
        start = segment_start
        duration = max(0.01, segment_end - start)
        weights = [max(1, len(token.strip(".,!?;:"))) for token in tokens]
        total_weight = sum(weights)
        cursor = start
        result = []
        for index, (token, weight) in enumerate(zip(tokens, weights)):
            end = float(segment["end"]) if index == len(tokens) - 1 else cursor + duration * weight / total_weight
            result.append({"text": token, "start": cursor, "end": end})
            cursor = end
        return result

    def group_caption_segments(self, segments: list[dict], max_words: int) -> list[dict]:
        max_words = max(1, int(max_words))
        grouped = []
        for segment in segments:
            words = self.caption_words_with_timing(segment)
            if not words:
                continue
            for start_index in range(0, len(words), max_words):
                chunk = words[start_index:start_index + max_words]
                grouped.append(
                    {
                        "start": float(chunk[0]["start"]),
                        "end": float(chunk[-1]["end"]),
                        "text": " ".join(str(word["text"]).strip() for word in chunk).strip(),
                        "words": chunk,
                    }
                )
        return grouped

    def ass_dialogue_line(self, start: float, end: float, text: str) -> str:
        return (
            f"Dialogue: 0,{self.format_ass_timestamp(start)},{self.format_ass_timestamp(end)},"
            f"Default,,0,0,0,,{text}\n"
        )

    def ass_escape(self, text: str) -> str:
        return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", "\\N")

    def ass_color(self, hex_color: str) -> str:
        value = self.clean_hex(hex_color, "#FFFFFF")
        return f"&H00{value[5:7]}{value[3:5]}{value[1:3]}"

    def ass_override_color(self, hex_color: str) -> str:
        value = self.clean_hex(hex_color, "#FFFFFF")
        return f"&H{value[5:7]}{value[3:5]}{value[1:3]}&"

    def ffmpeg_filter_path(self, path: Path) -> str:
        value = str(path.resolve()).replace("\\", "/").replace(":", "\\:")
        return "'" + value.replace("'", "\\'") + "'"

    def update_style_controls(self) -> None:
        enabled = self.use_speaking_style.isChecked()
        self.speaking_style.setEnabled(enabled)
        self.style_mode.setEnabled(enabled)
        self.refresh_segment_table()

    def refresh_profiles(self, selected: str = "") -> None:
        names = self.store.names()
        selected_name = selected or self.default_voice_profile_name
        if selected_name not in names:
            selected_name = ""
        profile_combos = [self.profile, self.voice_profile, self.moss_profile]
        if hasattr(self, "voice_design_source"):
            profile_combos.append(self.voice_design_source)
        for combo in profile_combos:
            combo.blockSignals(True)
            combo.clear()
            for name in names:
                combo.addItem(voice_display_name(name), name)
            if selected_name:
                selected_index = combo.findData(selected_name)
                combo.setCurrentIndex(selected_index if selected_index >= 0 else 0)
            combo.blockSignals(False)
        if hasattr(self, "chatterbox_v3_tab"):
            self.chatterbox_v3_tab.refresh_profiles()
        current_name = str(self.voice_profile.currentData() or self.profile.currentData() or "")
        if current_name:
            self.load_profile(current_name)
        else:
            self.reference_audio.clear()
            self.reference_text.clear()
        self.add_local_zonos2_profiles()
        self.update_default_voice_profile_button()

    def voice_design_settings(self) -> dict:
        return {
            "preset": self.voice_design_preset.currentText(),
            "gender_lock": self.voice_design_gender_lock.isChecked(),
            "pitch_semitones": self.voice_design_pitch.value(),
            "formant_semitones": self.voice_design_formant.value(),
            "warmth_db": self.voice_design_warmth.value(),
            "brightness_db": self.voice_design_brightness.value(),
            "speed": self.voice_design_speed.value(),
        }

    def voice_design_signature(self) -> str:
        payload = {
            "source": str(self.voice_design_source.currentData() or ""),
            "settings": self.voice_design_settings(),
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    def invalidate_voice_design_preview(self, *_args) -> None:
        self.voice_design_preview_signature = ""
        self.voice_design_play_preview_button.setEnabled(False)
        self.voice_design_save_button.setEnabled(False)

    def update_voice_design_gender_range(self, locked: bool) -> None:
        self.voice_design_pitch.setRange(-1.5 if locked else -3.5, 1.5 if locked else 3.5)
        self.voice_design_formant.setRange(-2.0 if locked else -4.0, 2.0 if locked else 4.0)
        self.invalidate_voice_design_preview()

    def apply_voice_design_preset(self, preset: str) -> None:
        values = {
            "Subtle variation": (0.0, 0.4, 0.8, 0.3, 1.00),
            "Warm and deeper": (-0.6, -0.8, 2.0, -0.5, 0.99),
            "Bright and younger": (0.6, 0.8, -0.3, 1.5, 1.01),
            "Calm and soft": (-0.3, -0.2, 1.0, -0.5, 0.97),
        }.get(preset)
        if values is None:
            return
        pitch, formant, warmth, brightness, speed = values
        self.voice_design_pitch.setValue(pitch)
        self.voice_design_formant.setValue(formant)
        self.voice_design_warmth.setValue(warmth)
        self.voice_design_brightness.setValue(brightness)
        self.voice_design_speed.setValue(speed)
        self.invalidate_voice_design_preview()

    def reset_voice_design_controls(self) -> None:
        self.voice_design_gender_lock.setChecked(True)
        self.voice_design_preset.setCurrentText("Subtle variation")
        self.apply_voice_design_preset("Subtle variation")

    def selected_voice_design_audio(self) -> tuple[str, dict, Path]:
        name = str(self.voice_design_source.currentData() or "")
        if not name:
            raise ValueError("Select a source voice profile first.")
        profile = self.store.load(name)
        audio_path = Path(str(profile.get("reference_audio", "")))
        if not audio_path.is_file():
            audio_path = self.store.root / name / "reference.wav"
        if not audio_path.is_file():
            raise ValueError("The selected source voice audio is missing.")
        return name, profile, audio_path

    def play_voice_audio_path(self, path: Path, label: str) -> None:
        if not path.is_file():
            raise ValueError("The audio file is missing.")
        if self.voice_preview_player is None:
            self.voice_preview_audio_output = QAudioOutput(self)
            self.voice_preview_audio_output.setVolume(1.0)
            self.voice_preview_player = QMediaPlayer(self)
            self.voice_preview_player.setAudioOutput(self.voice_preview_audio_output)
            self.voice_preview_player.playbackStateChanged.connect(
                self.on_voice_preview_state_changed
            )
        self.voice_preview_player.stop()
        self.voice_preview_player.setSource(QUrl.fromLocalFile(str(path.resolve())))
        self.voice_preview_player.play()
        self.voice_list_status.setText(label)

    def play_voice_design_original(self) -> None:
        try:
            name, _profile, audio_path = self.selected_voice_design_audio()
            self.play_voice_audio_path(
                audio_path, f"Playing original voice: {voice_display_name(name)}"
            )
        except Exception as exc:
            QMessageBox.warning(self, "Could not play original voice", str(exc))

    def play_voice_design_preview(self) -> None:
        try:
            if not self.voice_design_preview_path:
                raise ValueError("Generate a preview first.")
            self.play_voice_audio_path(
                self.voice_design_preview_path, "Playing designed voice preview."
            )
        except Exception as exc:
            QMessageBox.warning(self, "Could not play voice preview", str(exc))

    def generate_voice_design_preview(self) -> None:
        try:
            if self.thread and self.thread.isRunning():
                raise RuntimeError("Another task is already running.")
            name, _profile, audio_path = self.selected_voice_design_audio()
            self.stop_voice_preview()
            destination = app_data_dir() / "voice_designer" / "latest_preview.wav"
            settings = self.voice_design_settings()
            self.voice_design_pending_signature = self.voice_design_signature()
            self.voice_design_preview_path = None
            self.invalidate_voice_design_preview()
            self.active_task_ui = "voice_list"
            self.worker = VoiceDesignWorker(audio_path, destination, settings)
            self.thread = QThread()
            self.worker.moveToThread(self.thread)
            self.thread.started.connect(self.worker.run)
            self.worker.progress.connect(self.on_voice_design_progress)
            self.worker.completed.connect(self.on_voice_design_preview_completed)
            self.worker.failed.connect(self.on_voice_design_failed)
            self.worker.completed.connect(self.thread.quit)
            self.worker.failed.connect(self.thread.quit)
            self.thread.finished.connect(self.on_task_finished)
            self.set_busy(True, f"Designing variation from {voice_display_name(name)}...")
            self.append_log(
                f"Generating Voice Designer preview from {voice_display_name(name)}."
            )
            self.thread.start()
        except Exception as exc:
            QMessageBox.critical(self, "Could not generate voice preview", str(exc))

    def on_voice_design_progress(self, message: str) -> None:
        self.voice_list_status.setText(message)
        self.append_log(message)

    def on_voice_design_preview_completed(self, path: str) -> None:
        self.voice_design_preview_path = Path(path)
        self.voice_design_preview_signature = self.voice_design_pending_signature
        self.voice_design_play_preview_button.setEnabled(True)
        self.voice_design_save_button.setEnabled(True)
        message = "Voice Designer preview is ready. Compare Original and Preview before saving."
        self.voice_list_status.setText(message)
        self.append_log(message)

    def on_voice_design_failed(self, details: str) -> None:
        self.voice_design_preview_path = None
        self.invalidate_voice_design_preview()
        self.voice_list_status.setText("Could not generate Voice Designer preview.")
        self.append_log(details)
        QMessageBox.critical(self, "Voice Designer failed", details[-4000:])

    def save_voice_design_profile(self) -> None:
        try:
            if not self.voice_design_preview_path or not self.voice_design_preview_path.is_file():
                raise ValueError("Generate a voice preview first.")
            if self.voice_design_preview_signature != self.voice_design_signature():
                raise ValueError("Settings changed. Generate a new preview before saving.")
            name = self.voice_design_name.text().strip()
            _source_name, source_profile, _audio_path = self.selected_voice_design_audio()
            profile = self.store.save_designed_variant(
                name,
                self.voice_design_preview_path,
                source_profile,
                self.voice_design_settings(),
            )
            self.refresh_profiles(profile["name"])
            self.voice_design_name.clear()
            message = f"Designed voice profile '{profile['name']}' saved."
            self.voice_list_status.setText(message)
            self.append_log(message)
            QMessageBox.information(self, "Voice Designer", message)
        except Exception as exc:
            QMessageBox.critical(self, "Could not save designed voice", str(exc))

    def preview_selected_voice(self) -> None:
        try:
            if (
                self.voice_preview_player is not None
                and self.voice_preview_player.playbackState()
                == QMediaPlayer.PlaybackState.PlayingState
            ):
                self.stop_voice_preview()
                return
            name = str(self.profile.currentData() or "")
            if not name:
                raise ValueError("Select a voice profile first.")
            profile = self.store.load(name)
            audio_path = Path(profile.get("reference_audio", ""))
            if not audio_path.is_file():
                audio_path = self.store.root / name / "reference.wav"
            if not audio_path.is_file():
                raise ValueError("The reference audio for this voice profile is missing.")
            if self.voice_preview_player is None:
                self.voice_preview_audio_output = QAudioOutput(self)
                self.voice_preview_audio_output.setVolume(1.0)
                self.voice_preview_player = QMediaPlayer(self)
                self.voice_preview_player.setAudioOutput(self.voice_preview_audio_output)
                self.voice_preview_player.playbackStateChanged.connect(
                    self.on_voice_preview_state_changed
                )
            self.voice_preview_player.setSource(QUrl.fromLocalFile(str(audio_path.resolve())))
            self.voice_preview_player.play()
            self.preview_voice_button.setText("Stop preview")
            self.voice_list_status.setText(f"Previewing voice: {voice_display_name(name)}")
        except Exception as exc:
            self.stop_voice_preview()
            QMessageBox.warning(self, "Could not preview voice", str(exc))

    def on_voice_preview_state_changed(self, state) -> None:
        if state != QMediaPlayer.PlaybackState.PlayingState:
            self.preview_voice_button.setText("Preview voice")

    def stop_voice_preview(self) -> None:
        if self.voice_preview_player is not None:
            self.voice_preview_player.stop()
        self.preview_voice_button.setText("Preview voice")

    def delete_selected_voice(self) -> None:
        name = str(self.profile.currentData() or "")
        if not name:
            QMessageBox.warning(self, "Delete voice", "Select a voice profile first.")
            return
        answer = QMessageBox.question(
            self,
            "Delete voice",
            f"Permanently delete voice profile '{voice_display_name(name)}'?\n\n"
            "Its saved reference audio and profile data will also be removed.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.stop_voice_preview()
            names = self.store.names()
            deleted_index = names.index(name)
            self.store.delete(name)
            if name == self.default_voice_profile_name:
                self.default_voice_profile_name = ""
                self.persist_settings("voice_clone")
            remaining = self.store.names()
            next_name = remaining[min(deleted_index, len(remaining) - 1)] if remaining else ""
            self.refresh_profiles(next_name)
            self.voice_list_status.setText(
                f"Deleted voice profile: {voice_display_name(name)}"
            )
        except Exception as exc:
            QMessageBox.critical(self, "Could not delete voice", str(exc))

    def update_default_voice_profile_button(self) -> None:
        current = str(self.voice_profile.currentData() or "")
        is_default = bool(current) and current == self.default_voice_profile_name
        self.default_voice_profile_button.setEnabled(bool(current) and not is_default)
        self.default_voice_profile_button.setText("Default voice" if is_default else "Set default")

    def set_default_voice_profile(self) -> None:
        name = str(self.voice_profile.currentData() or "")
        if not name:
            QMessageBox.warning(self, "Default voice", "Select a voice profile first.")
            return
        self.default_voice_profile_name = name
        self.persist_settings("voice_clone")
        self.update_default_voice_profile_button()
        self.status.setText(f"Default voice profile saved: {voice_display_name(name)}")

    def add_local_zonos2_profiles(self) -> int:
        selected = self.zonos2_voice.currentData() or self.zonos2_voice.currentText()
        for index in range(self.zonos2_voice.count() - 1, -1, -1):
            if str(self.zonos2_voice.itemData(index) or "").startswith("profile:"):
                self.zonos2_voice.removeItem(index)
        names = self.store.names()
        for name in names:
            self.zonos2_voice.addItem(voice_display_name(name), f"profile:{name}")
        selected_index = self.zonos2_voice.findData(selected)
        if selected_index >= 0:
            self.zonos2_voice.setCurrentIndex(selected_index)
        return len(names)

    def load_profile(self, name: str) -> None:
        if not name:
            return
        profile = self.store.load(name)
        self.reference_audio.setText(profile["reference_audio"])
        self.reference_text.setPlainText(profile.get("reference_text", ""))
        language = profile.get("language", "en")
        self.clone_language.setCurrentIndex(max(0, self.clone_language.findData(language)))
        voice_index = self.language.findData(language)
        if voice_index >= 0:
            self.language.setCurrentIndex(voice_index)

    def pick_audio(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Reference voice", "", "Audio (*.wav *.mp3)")
        if path:
            self.reference_audio.setText(path)

    def auto_transcribe_selected_voice(self) -> None:
        try:
            if self.moss_qa_thread and self.moss_qa_thread.isRunning():
                raise RuntimeError("MOSS audio QA is already running.")
            if self.thread and self.thread.isRunning():
                raise RuntimeError("Another task is already running.")
            selected_name = str(self.profile.currentData() or "")
            audio_path = Path()
            if selected_name:
                profile = self.store.load(selected_name)
                audio_path = Path(profile.get("reference_audio", ""))
                if not audio_path.is_file():
                    audio_path = self.store.root / selected_name / "reference.wav"
            if not audio_path.is_file():
                audio_path = Path(self.reference_audio.text().strip())
            if not audio_path.is_file():
                raise ValueError(
                    "Select a saved voice or choose a valid reference MP3/WAV file first."
                )

            self.active_task_ui = "voice_list"
            self.worker = VoiceTranscriptWorker(
                audio_path, str(self.clone_language.currentData() or "en")
            )
            self.thread = QThread()
            self.worker.moveToThread(self.thread)
            self.thread.started.connect(self.worker.run)
            self.worker.progress.connect(self.on_voice_transcript_progress)
            self.worker.completed.connect(self.on_voice_transcript_completed)
            self.worker.failed.connect(self.on_voice_transcript_failed)
            self.worker.completed.connect(self.thread.quit)
            self.worker.failed.connect(self.thread.quit)
            self.thread.finished.connect(self.on_task_finished)
            label = voice_display_name(selected_name) if selected_name else audio_path.name
            self.set_busy(True, f"Transcribing voice: {label}...")
            self.append_log(f"Starting Whisper transcript for voice: {label}")
            self.thread.start()
        except Exception as exc:
            QMessageBox.critical(self, "Could not transcribe voice", str(exc))

    def on_voice_transcript_progress(self, message: str) -> None:
        self.voice_list_status.setText(message)
        self.append_log(message)

    def on_voice_transcript_completed(self, transcript: str) -> None:
        self.reference_text.setPlainText(transcript)
        message = "Transcript generated and filled into Reference transcript."
        self.voice_list_status.setText(message)
        self.append_log(message)

    def on_voice_transcript_failed(self, details: str) -> None:
        self.voice_list_status.setText("Could not generate voice transcript.")
        self.append_log(details)
        QMessageBox.critical(
            self, "Could not transcribe voice", details[-4000:]
        )

    def pick_input(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Script", "", "Script (*.srt *.txt)")
        if path:
            self.segment_style_overrides.clear()
            self.input_file.setText(path)
            if not self.output_dir.text():
                self.output_dir.setText(str(Path(path).with_name(Path(path).stem + "_voiceover")))
            self.refresh_segment_table()

    def pick_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Output folder")
        if path:
            self.active_output_dir = None
            self.output_dir.setText(path)
            self.refresh_segment_table()

    def append_text_segments(self, input_field: QLineEdit, text_input: QPlainTextEdit, name: str) -> int:
        additions = parse_paragraph_segments(text_input.toPlainText())
        if not additions:
            raise ValueError("Enter one or more text segments. Separate segments with a blank line.")
        scripts_dir = app_data_dir() / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        draft_path = scripts_dir / f"{name}_segments.txt"
        current_path = Path(input_field.text())
        existing: list[str] = []
        if current_path.is_file():
            if current_path.resolve() == draft_path.resolve():
                existing = [segment.text for segment in parse_input(draft_path)]
            else:
                existing = [segment.text for segment in parse_input(current_path)]
        draft_path.write_text("\n".join([*existing, *additions]) + "\n", encoding="utf-8")
        input_field.setText(str(draft_path))
        text_input.clear()
        return len(additions)

    def add_omnivoice_text_segments(self) -> None:
        try:
            count = self.append_text_segments(
                self.input_file, self.segment_text_input, "omnivoice"
            )
            self.segment_style_overrides.clear()
            self.refresh_segment_table()
            self.status.setText(f"Added {count} OmniVoice text segment(s).")
        except Exception as exc:
            QMessageBox.warning(self, "Cannot add text segments", str(exc))

    def add_zonos2_text_segments(self) -> None:
        try:
            count = self.append_text_segments(
                self.zonos2_input_file, self.zonos2_segment_text_input, "zonos2"
            )
            self.refresh_zonos2_range()
            self.refresh_zonos2_segment_table()
            self.zonos2_status.setText(f"Added {count} ZONOS2 text segment(s).")
        except Exception as exc:
            QMessageBox.warning(self, "Cannot add text segments", str(exc))

    def add_moss_batch_row(
        self, input_path: str = "", output_path: str = "", checked: bool = False,
        input_edit: QLineEdit | None = None, output_edit: QLineEdit | None = None,
    ) -> dict:
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)
        view_radio = QRadioButton()
        view_radio.setToolTip("Chọn task để xem danh sách segment bên phải")
        view_radio.setFixedWidth(20)
        input_edit = input_edit or QLineEdit(input_path)
        output_edit = output_edit or QLineEdit(output_path)
        input_edit.setPlaceholderText("SRT/TXT input file")
        output_edit.setPlaceholderText("Output folder")
        browse_input = QPushButton("Browse")
        browse_input.setFixedWidth(65)
        browse_output = QPushButton("Browse")
        browse_output.setFixedWidth(65)
        remove_button = QPushButton("✕")
        remove_button.setFixedWidth(28)
        remove_button.setStyleSheet(
            "color: #ff5555; font-weight: bold; background: #2d1818; border: 1px solid #552222;"
        )
        row_layout.addWidget(view_radio)
        row_layout.addWidget(input_edit, 3)
        row_layout.addWidget(browse_input)
        row_layout.addWidget(output_edit, 3)
        row_layout.addWidget(browse_output)
        row_layout.addWidget(remove_button)
        row = {
            "widget": row_widget,
            "view_radio": view_radio,
            "input_edit": input_edit,
            "output_edit": output_edit,
            "active_output_dir": None,
        }
        self.moss_batch_rows.append(row)
        self.moss_batch_layout.addWidget(row_widget)
        browse_input.clicked.connect(lambda: self.pick_moss_row_input(row))
        browse_output.clicked.connect(lambda: self.pick_moss_row_output(row))
        remove_button.clicked.connect(lambda: self.remove_moss_batch_row(row))
        view_radio.toggled.connect(lambda state: self.select_moss_batch_row(row) if state else None)
        input_edit.textChanged.connect(lambda _text: self.refresh_moss_segments() if row is self.moss_current_row else None)
        output_edit.textChanged.connect(lambda _text: self.refresh_moss_segments() if row is self.moss_current_row else None)
        if checked or self.moss_current_row is None:
            view_radio.setChecked(True)
            self.moss_current_row = row
        self.update_moss_batch_height()
        return row

    def add_moss_batch_row_clicked(self) -> None:
        self.add_moss_batch_row()

    def remove_moss_batch_row(self, row: dict) -> None:
        if len(self.moss_batch_rows) <= 1:
            QMessageBox.information(self, "Batch Queue", "You must have at least one task row.")
            return
        selected = row is self.moss_current_row
        self.moss_batch_rows.remove(row)
        self.moss_batch_layout.removeWidget(row["widget"])
        row["widget"].deleteLater()
        if selected:
            self.moss_current_row = self.moss_batch_rows[0]
            self.moss_current_row["view_radio"].setChecked(True)
            self.refresh_moss_segments()
        self.update_moss_batch_height()

    def update_moss_batch_height(self) -> None:
        visible_rows = min(4, max(1, len(self.moss_batch_rows)))
        self.moss_batch_scroll.setFixedHeight(visible_rows * 38 + 10)

    def select_moss_batch_row(self, row: dict) -> None:
        if row not in self.moss_batch_rows:
            return
        for other in self.moss_batch_rows:
            if other is not row and other["view_radio"].isChecked():
                other["view_radio"].blockSignals(True)
                other["view_radio"].setChecked(False)
                other["view_radio"].blockSignals(False)
        self.moss_current_row = row
        self.active_moss_output_dir = row.get("active_output_dir")
        if hasattr(self, "moss_segment_table"):
            self.refresh_moss_segments()

    def moss_active_input(self) -> QLineEdit:
        return self.moss_current_row["input_edit"] if self.moss_current_row else self.moss_input_file

    def moss_active_output(self) -> QLineEdit:
        return self.moss_current_row["output_edit"] if self.moss_current_row else self.moss_output_dir

    def pick_moss_row_input(self, row: dict) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "MOSS-TTS script", "", "Script (*.srt *.txt)")
        if path:
            row["input_edit"].setText(path)
            if not row["output_edit"].text().strip():
                source = Path(path)
                row["output_edit"].setText(str(source.with_name(source.stem + "_moss_tts")))
            row["active_output_dir"] = None
            if row is self.moss_current_row:
                self.active_moss_output_dir = None
                self.refresh_moss_segments()

    def pick_moss_row_output(self, row: dict) -> None:
        path = QFileDialog.getExistingDirectory(self, "MOSS-TTS output folder")
        if path:
            row["active_output_dir"] = None
            row["output_edit"].setText(path)
            if row is self.moss_current_row:
                self.active_moss_output_dir = None
                self.refresh_moss_segments()

    def pick_moss_input(self) -> None:
        if self.moss_current_row:
            self.pick_moss_row_input(self.moss_current_row)

    def pick_moss_output(self) -> None:
        if self.moss_current_row:
            self.pick_moss_row_output(self.moss_current_row)

    def add_moss_text_segments(self) -> None:
        try:
            count = self.append_text_segments(
                self.moss_active_input(), self.moss_segment_text_input, "moss_tts"
            )
            self.refresh_moss_segments()
            self.moss_status.setText(f"Added {count} MOSS-TTS text segment(s).")
        except Exception as exc:
            QMessageBox.warning(self, "Cannot add text segments", str(exc))

    def current_moss_session_dir(self, create: bool = False) -> Path | None:
        root_text = self.moss_active_output().text().strip()
        if not root_text:
            return None
        root = Path(root_text)
        row = self.moss_current_row
        active_dir = row.get("active_output_dir") if row else self.active_moss_output_dir
        if active_dir and (Path(active_dir).parent == root or Path(active_dir) == root):
            self.active_moss_output_dir = Path(active_dir)
            return self.active_moss_output_dir
        if create:
            root.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            candidate = root / f"moss_tts_{timestamp}"
            suffix = 1
            while candidate.exists():
                candidate = root / f"moss_tts_{timestamp}_{suffix:02d}"
                suffix += 1
            candidate.mkdir(parents=True)
            self.active_moss_output_dir = candidate
            if row:
                row["active_output_dir"] = candidate
            return candidate
        return None

    def moss_segment_audio_path(self, position: int) -> Path:
        total = max(1, self.moss_segment_table.rowCount())
        width = max(3, len(str(total)))
        directory = self.active_moss_output_dir or Path(self.moss_active_output().text())
        return directory / f"{position:0{width}d}.{self.moss_output_format.currentText()}"

    def refresh_moss_segments(self) -> None:
        path = Path(self.moss_active_input().text())
        if not path.is_file():
            self.moss_segment_table.setRowCount(0)
            return
        try:
            segments = parse_input(path)
        except Exception:
            self.moss_segment_table.setRowCount(0)
            return
        total = len(segments)
        self.moss_range_from.setRange(1, max(1, total))
        self.moss_range_to.setRange(1, max(1, total))
        self.moss_range_to.setValue(max(1, total))
        self.moss_segment_table.setRowCount(total)
        for row, segment in enumerate(segments):
            position = row + 1
            audio_path = self.moss_segment_audio_path(position)
            completed = audio_path.is_file() and audio_path.stat().st_size > 0
            timing = ""
            if segment.start_seconds is not None:
                timing = f"{segment.start_seconds:.2f}-{segment.end_seconds:.2f}"
            self.moss_segment_table.setItem(row, 0, QTableWidgetItem(str(position)))
            self.moss_segment_table.setItem(row, 1, QTableWidgetItem(timing))
            self.moss_segment_table.setItem(row, 2, QTableWidgetItem(segment.text))
            self.moss_segment_table.setItem(row, 3, QTableWidgetItem("Completed" if completed else "Pending"))
            actions = QWidget()
            action_layout = QHBoxLayout(actions)
            action_layout.setContentsMargins(0, 0, 0, 0)
            play = self.icon_button(QStyle.StandardPixmap.SP_MediaPlay, "Play", lambda checked=False, p=position: self.play_moss_segment(p))
            rerun = self.icon_button(QStyle.StandardPixmap.SP_BrowserReload, "Rerun and overwrite", lambda checked=False, p=position: self.start_moss(start_override=p, end_override=p, overwrite_override=True))
            delete = self.icon_button(QStyle.StandardPixmap.SP_TrashIcon, "Delete audio file", lambda checked=False, p=position: self.delete_moss_segment(p))
            play.setEnabled(completed)
            delete.setEnabled(completed)
            action_layout.addWidget(play)
            action_layout.addWidget(rerun)
            action_layout.addWidget(delete)
            self.moss_segment_table.setCellWidget(row, 4, actions)

    def start_moss_audio_check(
        self, positions: list[int] | None = None, auto_pipeline: bool = False
    ) -> bool:
        try:
            if isinstance(positions, bool):
                positions = None
            if positions is None:
                self.moss_review_list.clear()
                self.moss_review_items.clear()
                self.moss_review_reasons.clear()
            # The Check all button should also repair an existing session when the
            # user has enabled automatic QA; previously it only painted review labels.
            if not auto_pipeline and positions is None and self.moss_auto_qa_retry.isChecked():
                auto_pipeline = True
                self.moss_pipeline_phase = "initial_qa"
                self.moss_pipeline_retry_queue = []
                self.moss_pipeline_retry_counts = {}
                self.moss_pipeline_current_retry = None
                self.moss_pipeline_unresolved = []
                self.moss_pipeline_pending_recheck = []
                self.moss_retry_start_pending = False
                self.moss_pipeline_cancelled = False
                self.moss_job_succeeded = True
                self.moss_batch_running = False
                self.moss_batch_queue = []
                session = self.current_moss_session_dir()
                self.moss_batch_outputs = [str(session)] if session is not None else []
            if self.thread and self.thread.isRunning():
                raise RuntimeError("Another task is already running.")
            input_path = Path(self.moss_active_input().text())
            if not input_path.is_file():
                raise ValueError("Choose the source TXT/SRT file before checking audio.")
            segments = parse_input(input_path)
            allowed_positions = set(positions or range(1, len(segments) + 1))
            jobs = [
                (position, segment.text, self.moss_segment_audio_path(position))
                for position, segment in enumerate(segments, start=1)
                if position in allowed_positions and self.moss_segment_audio_path(position).is_file()
            ]
            if not jobs:
                if auto_pipeline:
                    raise ValueError("No generated files were found for automatic MOSS audio QA.")
                if not self.select_existing_moss_session():
                    return False
                jobs = [
                    (position, segment.text, self.moss_segment_audio_path(position))
                    for position, segment in enumerate(segments, start=1)
                    if position in allowed_positions and self.moss_segment_audio_path(position).is_file()
                ]
            if not jobs:
                raise ValueError(
                    "The selected folder contains no numbered audio matching the source segments."
                )
            output_dir = jobs[0][2].parent
            if auto_pipeline and not self.moss_batch_outputs:
                self.moss_batch_outputs = [str(output_dir)]
            self.active_task_ui = "moss"
            self.moss_qa_worker = MossAudioCheckWorker(
                jobs, output_dir, str(self.moss_language.currentData() or "en"),
                self.moss_asr_workers.value(),
            )
            self.moss_audio_check_auto_pipeline = auto_pipeline
            self.moss_last_qa_reviews = []
            self.moss_last_qa_failed = False
            self.moss_last_qa_cancelled = False
            self.moss_qa_round_phase = self.moss_pipeline_phase if auto_pipeline else "manual"
            self.moss_qa_round_finished = False
            self.moss_qa_requested_positions = [job[0] for job in jobs]
            self.moss_qa_thread = QThread()
            self.moss_qa_worker.moveToThread(self.moss_qa_thread)
            self.moss_qa_thread.started.connect(self.moss_qa_worker.run)
            self.moss_qa_worker.progress.connect(self.on_progress)
            self.moss_qa_worker.segment_status.connect(self.on_moss_parallel_qa_status)
            self.moss_qa_worker.review_detected.connect(self.on_moss_review_detected)
            self.moss_qa_worker.completed.connect(self.on_moss_audio_check_completed)
            self.moss_qa_worker.cancelled.connect(self.on_moss_audio_check_cancelled)
            self.moss_qa_worker.failed.connect(self.on_moss_audio_check_failed)
            self.moss_qa_worker.completed.connect(self.moss_qa_thread.quit)
            self.moss_qa_worker.cancelled.connect(self.moss_qa_thread.quit)
            self.moss_qa_worker.failed.connect(self.moss_qa_thread.quit)
            self.moss_qa_thread.finished.connect(self.on_moss_audio_check_thread_finished)
            self.set_busy(True, f"Checking {len(jobs)} MOSS audio file(s)...")
            self.moss_progress.setRange(0, len(jobs))
            self.moss_progress.setValue(0)
            self.append_log(
                f"Audio QA started for {len(jobs)} file(s). "
                "Obvious duration runaways are flagged without ASR; normal files use CPU ASR."
            )
            self.moss_qa_thread.start()
            return True
        except Exception as exc:
            if auto_pipeline:
                self.append_log("Automatic MOSS audio QA could not start: " + str(exc))
                self.moss_last_qa_failed = True
                QTimer.singleShot(0, self.start_moss_post_qa_processing)
            else:
                QMessageBox.warning(self, "Cannot check MOSS audio", str(exc))
            return False

    def select_existing_moss_session(self) -> bool:
        start_dir = self.active_moss_output_dir
        if start_dir is None:
            output_text = self.moss_active_output().text().strip()
            start_dir = Path(output_text) if output_text else None
        selected = QFileDialog.getExistingDirectory(
            self,
            "Select an existing MOSS session folder containing numbered WAV/MP3 files",
            str(start_dir) if start_dir else "",
        )
        if not selected:
            return False
        session_dir = Path(selected)
        numbered_audio = [
            path for path in session_dir.iterdir()
            if path.is_file()
            and re.fullmatch(r"\d+\.(wav|mp3)", path.name, re.IGNORECASE)
        ]
        if not numbered_audio:
            QMessageBox.warning(
                self,
                "Invalid MOSS session",
                "This folder does not contain numbered audio files such as 001.wav or 001.mp3.",
            )
            return False
        extensions = [path.suffix.lower().lstrip(".") for path in numbered_audio]
        detected_format = max(set(extensions), key=extensions.count)
        self.moss_output_format.setCurrentText(detected_format)
        self.active_moss_output_dir = session_dir
        self.moss_review_list.clear()
        self.moss_review_items.clear()
        self.moss_review_reasons.clear()
        if self.moss_current_row:
            self.moss_current_row["active_output_dir"] = session_dir
            if not self.moss_current_row["output_edit"].text().strip():
                self.moss_current_row["output_edit"].setText(str(session_dir.parent))
        self.refresh_moss_segments()
        self.persist_settings("voice_clone_v2")
        self.moss_status.setText(
            f"Existing session selected: {session_dir} · {len(numbered_audio)} audio file(s)"
        )
        return True

    def on_moss_audio_check_completed(self, message: str) -> None:
        self.moss_last_qa_reviews = list(
            getattr(self.moss_qa_worker, "review_positions", [])
        )
        # Reconcile from the worker's final result as well as the streaming signal.
        # This guarantees every failed row enters the repair queue even if the GUI
        # event loop was briefly busy when review_detected was emitted.
        reasons = dict(getattr(self.moss_qa_worker, "review_reasons", {}))
        for position in self.moss_last_qa_reviews:
            reason = reasons.get(position, "ASR verification failed")
            self.moss_review_reasons[position] = reason
            self.update_moss_review_entry(position, "Needs review", reason)
            if (
                getattr(self, "moss_audio_check_auto_pipeline", False)
                and position != self.moss_pipeline_current_retry
                and position not in self.moss_pipeline_retry_queue
                and position not in self.moss_pipeline_pending_recheck
                and self.moss_pipeline_retry_counts.get(position, 0)
                    < self.moss_auto_qa_max_retries.value()
            ):
                self.moss_pipeline_retry_queue.append(position)
        self.moss_status.setText(message)
        self.append_log(message)
        if getattr(self, "moss_audio_check_auto_pipeline", False):
            self.append_log(
                "Automatic repair queue: "
                + (", ".join(map(str, self.moss_pipeline_retry_queue)) or "already processing")
            )
            QTimer.singleShot(0, self.maybe_start_immediate_moss_retry)

    def on_moss_audio_check_cancelled(self, message: str) -> None:
        self.moss_last_qa_failed = True
        self.moss_last_qa_cancelled = True
        self.moss_pipeline_cancelled = True
        self.moss_status.setText(message)
        self.append_log(message)

    def on_moss_audio_check_failed(self, details: str) -> None:
        self.moss_last_qa_failed = True
        self.moss_status.setText("MOSS audio check failed.")
        self.append_log("MOSS audio check failed:\n" + details)

    def on_moss_parallel_qa_status(self, position: int, status: str) -> None:
        if (
            getattr(self, "moss_audio_check_auto_pipeline", False)
            and self.moss_qa_round_phase == "retry_qa"
            and status == "Verified"
        ):
            self.on_moss_segment_status(position, "Auto-fixed · Listen")
            self.update_moss_review_entry(position, "Auto-fixed · Listen")
        else:
            self.on_moss_segment_status(position, status)

    def on_moss_review_detected(self, position: int, reason: str) -> None:
        self.moss_review_reasons[position] = reason
        self.update_moss_review_entry(position, "Needs review", reason)
        if not getattr(self, "moss_audio_check_auto_pipeline", False):
            self.append_log(f"QA issue in segment {position}: {reason}")
            return
        attempts = self.moss_pipeline_retry_counts.get(position, 0)
        if attempts >= self.moss_auto_qa_max_retries.value():
            if position not in self.moss_pipeline_unresolved:
                self.moss_pipeline_unresolved.append(position)
            self.on_moss_segment_status(position, "Review required · Listen")
            self.update_moss_review_entry(position, "Review required · Listen", reason)
            self.append_log(
                f"Segment {position} still failed QA after {attempts} attempt(s): {reason}"
            )
            return
        if (
            position != self.moss_pipeline_current_retry
            and position not in self.moss_pipeline_retry_queue
        ):
            self.moss_pipeline_retry_queue.append(position)
            self.append_log(
                f"ASR detected segment {position}: {reason}. Queued for immediate rerender."
            )
        self.maybe_start_immediate_moss_retry()

    def update_moss_review_entry(
        self, position: int, state: str, reason: str | None = None
    ) -> None:
        if reason:
            self.moss_review_reasons[position] = reason
        detail = self.moss_review_reasons.get(position, "")
        text = f"#{position:03d} · {state}"
        if detail:
            text += f" · {detail}"
        item = self.moss_review_items.get(position)
        if item is None:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, position)
            self.moss_review_items[position] = item
            self.moss_review_list.addItem(item)
        item.setText(text)
        item.setToolTip(text)
        if state.startswith("Auto-fixed"):
            item.setForeground(QColor("#67d98b"))
        elif "rerender" in state.lower() or "Awaiting" in state:
            item.setForeground(QColor("#f1c75b"))
        else:
            item.setForeground(QColor("#ff6868"))
        # Keep the main segment table synchronized even when this entry came
        # from end-of-round reconciliation rather than the streaming signal.
        self.on_moss_segment_status(position, state)
        if 1 <= position <= self.moss_segment_table.rowCount():
            status_item = self.moss_segment_table.item(position - 1, 3)
            if status_item is not None:
                status_item.setToolTip(detail or state)

    def open_moss_review_item(self, item: QListWidgetItem) -> None:
        position = int(item.data(Qt.ItemDataRole.UserRole) or 0)
        if not 1 <= position <= self.moss_segment_table.rowCount():
            return
        row_item = self.moss_segment_table.item(position - 1, 0)
        self.moss_segment_table.selectRow(position - 1)
        if row_item is not None:
            self.moss_segment_table.scrollToItem(
                row_item, QAbstractItemView.ScrollHint.PositionAtCenter
            )
        if self.moss_segment_audio_path(position).is_file():
            self.play_moss_segment(position)

    def on_moss_audio_check_thread_finished(self) -> None:
        auto_pipeline = bool(getattr(self, "moss_audio_check_auto_pipeline", False))
        self.moss_qa_worker = None
        self.moss_qa_thread = None
        self.moss_qa_round_finished = True
        if auto_pipeline:
            if self.moss_last_qa_cancelled:
                self.moss_pipeline_phase = "idle"
                self.moss_batch_running = False
                self.moss_batch_queue = []
            elif self.moss_last_qa_failed:
                QTimer.singleShot(0, self.start_moss_post_qa_processing)
            else:
                QTimer.singleShot(0, self.maybe_start_immediate_moss_retry)
        elif not (self.thread and self.thread.isRunning()):
            self.set_busy(False)

    def play_moss_segment(self, position: int) -> None:
        path = self.moss_segment_audio_path(position)
        if path.is_file():
            os.startfile(path)

    def delete_moss_segment(self, position: int) -> None:
        path = self.moss_segment_audio_path(position)
        if path.is_file():
            path.unlink()
        self.refresh_moss_segments()

    def render_moss_preview(self) -> None:
        self.start_moss(segment_limit=self.moss_preview_count.value())

    def render_moss_range(self) -> None:
        self.start_moss(
            start_override=self.moss_range_from.value(),
            end_override=self.moss_range_to.value(),
            overwrite_override=self.moss_overwrite.isChecked(),
        )

    def start_moss(
        self, segment_limit: int | None = None, start_override: int | None = None,
        end_override: int | None = None, overwrite_override: bool | None = None,
        batch_row: dict | None = None,
        pipeline_retry: bool = False,
    ) -> None:
        try:
            if self.thread and self.thread.isRunning():
                raise RuntimeError("Another task is already running.")
            if (
                not pipeline_retry and self.moss_qa_thread
                and self.moss_qa_thread.isRunning()
            ):
                raise RuntimeError("MOSS audio QA is still running.")
            self.active_task_ui = "moss"
            if not pipeline_retry:
                self.persist_settings("voice_clone_v2")
            if batch_row is None and not self.moss_batch_running and not pipeline_retry:
                self.moss_batch_outputs = []
            if (
                not pipeline_retry and batch_row is None and segment_limit is None
                and start_override is None and end_override is None
            ):
                valid_rows = [
                    row for row in self.moss_batch_rows
                    if row["input_edit"].text().strip() and row["output_edit"].text().strip()
                ]
                if len(valid_rows) > 1:
                    self.moss_batch_queue = valid_rows
                    self.moss_batch_outputs = []
                    self.moss_batch_index = 0
                    self.moss_batch_running = True
                    self._start_next_moss_batch_item()
                    return
                if len(valid_rows) == 1 and valid_rows[0] is not self.moss_current_row:
                    self.select_moss_batch_row(valid_rows[0])
                    valid_rows[0]["view_radio"].setChecked(True)
            profile_name = str(self.moss_profile.currentData() or "")
            if not profile_name:
                raise ValueError("Create or select a saved voice profile first.")
            input_path = Path(self.moss_active_input().text())
            if not input_path.is_file():
                raise ValueError("Choose a valid MOSS-TTS SRT/TXT input file.")
            segments = parse_input(input_path)
            start = start_override or 1
            end = end_override or len(segments)
            if start > end:
                raise ValueError("Render range start must be less than or equal to end.")
            output_dir = self.current_moss_session_dir(create=True)
            if output_dir is None:
                raise ValueError("Choose a MOSS-TTS output folder.")
            if segment_limit:
                output_dir = output_dir / "_preview"
            overwrite = bool(overwrite_override)
            if overwrite and not pipeline_retry:
                existing = [self.moss_segment_audio_path(p) for p in range(start, end + 1) if self.moss_segment_audio_path(p).is_file()]
                if existing:
                    answer = QMessageBox.question(
                        self, "Overwrite existing MOSS-TTS files?",
                        f"{len(existing)} existing file(s) in range {start}-{end} will be overwritten.",
                    )
                    if answer != QMessageBox.StandardButton.Yes:
                        return
            if not pipeline_retry:
                check_end = min(end, segment_limit or end)
                self.moss_pipeline_phase = "initial_render"
                self.moss_pipeline_check_positions = list(range(start, check_end + 1))
                self.moss_pipeline_retry_queue = []
                self.moss_pipeline_retry_counts = {}
                self.moss_pipeline_current_retry = None
                self.moss_pipeline_unresolved = []
                self.moss_pipeline_pending_recheck = []
                self.moss_retry_start_pending = False
                self.moss_qa_round_finished = False
                self.moss_pipeline_cancelled = False
                self.moss_review_list.clear()
                self.moss_review_items.clear()
                self.moss_review_reasons.clear()
            self.worker = MossTTSWorker(
                self.store.load(profile_name), input_path, output_dir,
                self.selected_moss_checkpoint(),
                str(self.moss_device.currentData()), str(self.moss_dtype.currentData()),
                str(self.moss_attention.currentData()), str(self.moss_language.currentData()),
                self.moss_max_new_tokens.value(), self.moss_output_format.currentText(),
                segment_limit, self.moss_cooldown.value(), start, end, overwrite,
                self.moss_normalize.isChecked() and not self.moss_auto_qa_retry.isChecked(),
                self.moss_auto_duration.isChecked(),
                True,
            )
            self.moss_job_succeeded = False
            self.thread = QThread()
            self.worker.moveToThread(self.thread)
            self.thread.started.connect(self.worker.run)
            self.worker.progress.connect(self.on_progress)
            self.worker.timing.connect(self.on_moss_timing)
            self.worker.segment_status.connect(self.on_moss_segment_status)
            self.worker.completed.connect(self.on_moss_completed)
            self.worker.cancelled.connect(self.on_moss_cancelled)
            self.worker.failed.connect(self.on_moss_failed)
            self.worker.completed.connect(self.thread.quit)
            self.worker.cancelled.connect(self.thread.quit)
            self.worker.failed.connect(self.thread.quit)
            self.thread.finished.connect(self.on_moss_thread_finished)
            self.render_started_at = time.monotonic()
            batch_label = (
                f"Batch {self.moss_batch_index + 1}/{len(self.moss_batch_queue)} · "
                if self.moss_batch_running else ""
            )
            self.set_busy(True, batch_label + "Loading MOSS-TTS v1.5 local transformer...")
            timing_total = min(len(segments), segment_limit) if segment_limit else max(0, end - start + 1)
            self.reset_moss_timing(timing_total)
            self.moss_progress.setRange(0, timing_total)
            self.thread.start()
        except Exception as exc:
            if self.moss_batch_running and not pipeline_retry:
                self.moss_batch_running = False
            QMessageBox.critical(self, "Cannot render with MOSS-TTS", str(exc))

    def _start_next_moss_batch_item(self) -> None:
        row = self.moss_batch_queue[self.moss_batch_index]
        row["view_radio"].setChecked(True)
        self.select_moss_batch_row(row)
        self.start_moss(batch_row=row)

    @staticmethod
    def format_moss_duration(seconds: float) -> str:
        total = max(0, int(round(seconds)))
        hours, remainder = divmod(total, 3600)
        minutes, secs = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def reset_moss_timing(self, total: int) -> None:
        self.moss_timing_started_at = time.monotonic()
        self.moss_timing_total = max(0, total)
        self.moss_timing_completed = 0
        self.moss_timing_samples = []
        self.moss_timing_label.setText(
            "Elapsed 00:00:00 · ETA waiting for first completed segment"
        )
        self.moss_timing_timer.start()

    def on_moss_timing(
        self, completed: int, total: int, worker_elapsed: float, segment_seconds: float
    ) -> None:
        self.moss_timing_completed = completed
        self.moss_timing_total = total
        if segment_seconds > 0:
            self.moss_timing_samples.append(segment_seconds)
            self.moss_timing_samples = self.moss_timing_samples[-10:]
        self.update_moss_timing_clock()

    def update_moss_timing_clock(self) -> None:
        if self.moss_timing_started_at is None:
            return
        elapsed = time.monotonic() - self.moss_timing_started_at
        batch_prefix = (
            f"Batch {self.moss_batch_index + 1}/{len(self.moss_batch_queue)} · "
            if self.moss_batch_running and self.moss_batch_queue else ""
        )
        if not self.moss_timing_samples:
            self.moss_timing_label.setText(
                f"{batch_prefix}Elapsed {self.format_moss_duration(elapsed)} · "
                "ETA waiting for first completed segment"
            )
            return
        average = sum(self.moss_timing_samples) / len(self.moss_timing_samples)
        remaining_segments = max(0, self.moss_timing_total - self.moss_timing_completed)
        eta = average * remaining_segments
        estimated_total = elapsed + eta
        finish_at = datetime.fromtimestamp(time.time() + eta).strftime("%H:%M:%S")
        last = self.moss_timing_samples[-1]
        self.moss_timing_label.setText(
            f"{batch_prefix}Elapsed {self.format_moss_duration(elapsed)} · "
            f"Last {last:.1f}s · Avg {average:.1f}s/segment · "
            f"ETA {self.format_moss_duration(eta)} · "
            f"Estimated total {self.format_moss_duration(estimated_total)} · "
            f"Finish ~{finish_at}"
        )

    def on_moss_completed(self, output_dir: str) -> None:
        elapsed = time.monotonic() - self.render_started_at if self.render_started_at else 0
        duration = time.strftime("%H:%M:%S", time.gmtime(elapsed))
        self.moss_job_succeeded = True
        if self.moss_pipeline_phase == "initial_render":
            self.moss_batch_outputs.append(output_dir)
        self.moss_status.setText(f"Completed in {duration}: {output_dir}")
        self.moss_timing_timer.stop()
        self.moss_timing_completed = self.moss_timing_total
        self.update_moss_timing_clock()
        self.append_log(self.moss_status.text())
        if self.moss_pipeline_phase == "initial_render":
            self.refresh_moss_segments()
        completed_dir = Path(output_dir)
        if completed_dir.is_dir():
            self.active_moss_output_dir = completed_dir
            if self.moss_current_row:
                self.moss_current_row["active_output_dir"] = completed_dir
            self.persist_settings("voice_clone_v2")

    def on_moss_cancelled(self, message: str) -> None:
        self.moss_timing_timer.stop()
        self.moss_job_succeeded = False
        self.moss_batch_running = False
        self.moss_pipeline_cancelled = True
        self.moss_status.setText(message)
        self.append_log(message)
        QMessageBox.information(self, "MOSS-TTS stopped", message)

    def on_moss_failed(self, details: str) -> None:
        self.moss_timing_timer.stop()
        self.moss_job_succeeded = False
        if self.moss_pipeline_phase != "retry_render":
            self.moss_batch_running = False
        self.moss_status.setText("MOSS-TTS render failed")
        self.append_log(details)
        if self.moss_pipeline_phase != "retry_render":
            self.refresh_moss_segments()
        QMessageBox.critical(self, "MOSS-TTS render failed", details[-4000:])

    def on_moss_thread_finished(self) -> None:
        self.worker = None
        self.thread = None
        if self.moss_qa_thread and self.moss_qa_thread.isRunning():
            self.set_busy(True, "Parallel ASR continues while rerender queue is processed...")
        else:
            self.set_busy(False)
        if self.moss_pipeline_cancelled:
            self.moss_pipeline_phase = "idle"
            self.moss_batch_running = False
            self.moss_batch_queue = []
            return
        if self.moss_job_succeeded and self.moss_pipeline_phase == "initial_render":
            if self.moss_auto_qa_retry.isChecked():
                self.moss_pipeline_phase = "initial_qa"
                QTimer.singleShot(
                    100,
                    lambda: self.start_moss_audio_check(
                        self.moss_pipeline_check_positions, auto_pipeline=True
                    ),
                )
                return
            self.finish_moss_pipeline_item()
            return
        if self.moss_job_succeeded and self.moss_pipeline_phase == "retry_render":
            position = self.moss_pipeline_current_retry
            if position is not None:
                self.moss_pipeline_pending_recheck.append(position)
                self.on_moss_segment_status(position, "Rerendered · Awaiting ASR")
                self.update_moss_review_entry(position, "Rerendered · Awaiting ASR")
            self.moss_pipeline_current_retry = None
            QTimer.singleShot(0, self.maybe_start_immediate_moss_retry)
            return
        if not self.moss_job_succeeded and self.moss_pipeline_phase == "retry_render":
            position = self.moss_pipeline_current_retry
            if position is not None:
                if position not in self.moss_pipeline_unresolved:
                    self.moss_pipeline_unresolved.append(position)
                self.on_moss_segment_status(position, "Review required · Listen")
                self.update_moss_review_entry(position, "Review required · Listen")
            self.moss_pipeline_current_retry = None
            QTimer.singleShot(0, self.maybe_start_immediate_moss_retry)
            return
        self.finish_moss_pipeline_item()

    def continue_moss_pipeline_after_qa(self) -> None:
        if self.moss_last_qa_failed:
            self.append_log("Automatic QA stopped; continuing the requested post-processing.")
            self.start_moss_post_qa_processing()
            return
        reviews = list(self.moss_last_qa_reviews)
        if self.moss_pipeline_phase == "initial_qa":
            self.moss_pipeline_retry_queue = reviews
            if reviews:
                self.append_log(
                    "Automatic QA found segments requiring regeneration: "
                    + ", ".join(map(str, reviews))
                )
                self.start_next_moss_auto_retry()
            else:
                self.start_moss_post_qa_processing()
            return
        if self.moss_pipeline_phase == "retry_qa":
            position = self.moss_pipeline_current_retry
            if position is None:
                self.start_moss_post_qa_processing()
                return
            if position in reviews:
                attempts = self.moss_pipeline_retry_counts.get(position, 0)
                if attempts < self.moss_auto_qa_max_retries.value():
                    self.append_log(
                        f"Segment {position} still needs review after attempt {attempts}; retrying."
                    )
                    self.start_next_moss_auto_retry(retry_same=True)
                    return
                self.moss_pipeline_unresolved.append(position)
                self.on_moss_segment_status(position, "Review required · Listen")
            else:
                self.on_moss_segment_status(position, "Auto-fixed · Listen")
            if self.moss_pipeline_retry_queue and self.moss_pipeline_retry_queue[0] == position:
                self.moss_pipeline_retry_queue.pop(0)
            self.moss_pipeline_current_retry = None
            self.start_next_moss_auto_retry()

    def maybe_start_immediate_moss_retry(self) -> None:
        if self.moss_pipeline_cancelled:
            return
        if self.moss_retry_start_pending:
            return
        if self.thread and self.thread.isRunning():
            return
        if self.moss_pipeline_retry_queue:
            position = self.moss_pipeline_retry_queue.pop(0)
            self.moss_pipeline_current_retry = position
            attempt = self.moss_pipeline_retry_counts.get(position, 0) + 1
            self.moss_pipeline_retry_counts[position] = attempt
            self.moss_pipeline_phase = "retry_render"
            self.on_moss_segment_status(
                position,
                f"Auto rerender {attempt}/{self.moss_auto_qa_max_retries.value()}",
            )
            self.update_moss_review_entry(
                position,
                f"Auto rerender {attempt}/{self.moss_auto_qa_max_retries.value()}",
            )
            self.append_log(
                f"Immediately rerendering segment {position} while parallel ASR continues "
                f"({attempt}/{self.moss_auto_qa_max_retries.value()})."
            )
            self.moss_retry_start_pending = True
            QTimer.singleShot(
                0,
                lambda p=position: self.launch_immediate_moss_retry(p),
            )
            return
        if not self.moss_qa_round_finished:
            return
        if self.moss_pipeline_pending_recheck:
            positions = list(dict.fromkeys(self.moss_pipeline_pending_recheck))
            self.moss_pipeline_pending_recheck = []
            self.moss_pipeline_phase = "retry_qa"
            self.moss_qa_round_finished = False
            QTimer.singleShot(
                50,
                lambda p=positions: self.start_moss_audio_check(p, auto_pipeline=True),
            )
            return
        self.start_moss_post_qa_processing()

    def launch_immediate_moss_retry(self, position: int) -> None:
        self.moss_retry_start_pending = False
        self.start_moss(
            start_override=position,
            end_override=position,
            overwrite_override=True,
            pipeline_retry=True,
        )
        if self.thread is None:
            if position not in self.moss_pipeline_unresolved:
                self.moss_pipeline_unresolved.append(position)
            self.on_moss_segment_status(position, "Review required · Listen")
            self.moss_pipeline_current_retry = None
            QTimer.singleShot(0, self.maybe_start_immediate_moss_retry)

    def start_next_moss_auto_retry(self, retry_same: bool = False) -> None:
        if not self.moss_pipeline_retry_queue:
            self.start_moss_post_qa_processing()
            return
        position = self.moss_pipeline_retry_queue[0]
        self.moss_pipeline_current_retry = position
        attempt = self.moss_pipeline_retry_counts.get(position, 0) + 1
        self.moss_pipeline_retry_counts[position] = attempt
        self.moss_pipeline_phase = "retry_render"
        self.on_moss_segment_status(
            position,
            f"Auto rerender {attempt}/{self.moss_auto_qa_max_retries.value()}",
        )
        self.append_log(
            f"Automatically rerendering segment {position}, attempt "
            f"{attempt}/{self.moss_auto_qa_max_retries.value()}..."
        )
        QTimer.singleShot(
            100,
            lambda p=position: self.start_moss(
                start_override=p,
                end_override=p,
                overwrite_override=True,
                pipeline_retry=True,
            ),
        )

    def start_moss_post_qa_processing(self) -> None:
        if self.moss_normalize.isChecked():
            source = self.current_moss_session_dir()
            input_path = Path(self.moss_active_input().text())
            segments = parse_input(input_path) if input_path.is_file() else []
            expected = [self.moss_segment_audio_path(i) for i in range(1, len(segments) + 1)]
            if source is not None and expected and all(path.is_file() for path in expected):
                self.moss_pipeline_phase = "normalize"
                self.worker = NormalizeBatchWorker(
                    source,
                    self.moss_output_format.currentText(),
                    originals_dir_name="_original_moss_tts",
                )
                self.thread = QThread()
                self.worker.moveToThread(self.thread)
                self.thread.started.connect(self.worker.run)
                self.worker.progress.connect(self.on_merge_progress)
                self.worker.completed.connect(self.on_moss_pipeline_normalized)
                self.worker.failed.connect(self.on_moss_pipeline_normalize_failed)
                self.worker.completed.connect(self.thread.quit)
                self.worker.failed.connect(self.thread.quit)
                self.thread.finished.connect(self.on_moss_pipeline_normalize_thread_finished)
                self.set_busy(True, "QA complete · Normalizing completed MOSS batch...")
                self.thread.start()
                return
            self.append_log(
                "Normalize skipped because the current session does not contain every source segment."
            )
        self.finish_moss_pipeline_item()

    def on_moss_pipeline_normalized(self, source: str) -> None:
        self.moss_status.setText(f"QA and normalization completed: {source}")
        self.append_log(self.moss_status.text())

    def on_moss_pipeline_normalize_failed(self, details: str) -> None:
        self.append_log("MOSS normalization failed after QA:\n" + details)
        self.moss_status.setText("QA completed, but normalization failed.")

    def on_moss_pipeline_normalize_thread_finished(self) -> None:
        self.worker = None
        self.thread = None
        self.set_busy(False)
        QTimer.singleShot(0, self.finish_moss_pipeline_item)

    def finish_moss_pipeline_item(self) -> None:
        self.moss_pipeline_phase = "idle"
        if (
            self.moss_batch_running and self.moss_job_succeeded
            and self.moss_batch_index + 1 < len(self.moss_batch_queue)
        ):
            self.moss_batch_index += 1
            QTimer.singleShot(100, self._start_next_moss_batch_item)
            return
        if self.moss_job_succeeded:
            QApplication.beep()
            if self.moss_batch_running:
                total = len(self.moss_batch_outputs)
                self.moss_status.setText(f"Batch completed: {total} task(s).")
                QMessageBox.information(
                    self, "MOSS-TTS batch completed",
                    f"Completed {total} task(s).\n\n" + "\n".join(self.moss_batch_outputs),
                )
            elif self.moss_batch_outputs:
                output = self.moss_batch_outputs[-1]
                qa_note = (
                    "\n\nUnresolved segments: " + ", ".join(map(str, self.moss_pipeline_unresolved))
                    if self.moss_pipeline_unresolved else
                    "\n\nAutomatic ASR verification completed. Auto-fixed rows are marked for listening."
                )
                QMessageBox.information(
                    self, "MOSS-TTS completed", f"Audio files saved to:\n{output}{qa_note}"
                )
        self.moss_batch_running = False
        self.moss_batch_queue = []

    def merge_moss_audio(self) -> None:
        try:
            source = self.current_moss_session_dir()
            if source is None or not source.is_dir():
                raise ValueError("No active MOSS-TTS render session exists.")
            self.active_task_ui = "moss"
            self.worker = MergeWorker(source, self.moss_output_format.currentText(), self.moss_merge_pause.value())
            self.thread = QThread()
            self.worker.moveToThread(self.thread)
            self.thread.started.connect(self.worker.run)
            self.worker.progress.connect(self.on_merge_progress)
            self.worker.completed.connect(self.on_merge_completed)
            self.worker.failed.connect(self.on_merge_failed)
            self.worker.completed.connect(self.thread.quit)
            self.worker.failed.connect(self.thread.quit)
            self.thread.finished.connect(self.on_task_finished)
            self.set_busy(True, "Preparing MOSS-TTS audio merge...")
            self.thread.start()
        except Exception as exc:
            QMessageBox.critical(self, "Cannot merge MOSS-TTS audio", str(exc))

    def open_moss_output_folder(self) -> None:
        path = self.current_moss_session_dir() or Path(self.moss_active_output().text())
        if path.is_dir():
            os.startfile(path)
        else:
            QMessageBox.warning(self, "Output folder", "The output folder does not exist yet.")

    def pick_zonos2_input(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "ZONOS2 script", "", "Script (*.srt *.txt)")
        if path:
            self.zonos2_input_file.setText(path)
            if not self.zonos2_output_dir.text():
                self.zonos2_output_dir.setText(str(Path(path).with_name(Path(path).stem + "_zonos2")))
            self.refresh_zonos2_range()

    def refresh_zonos2_voices(self) -> None:
        try:
            server_url = self.zonos2_server_url.text().strip().rstrip("/")
            if not server_url.startswith(("http://", "https://")):
                raise ValueError("ZONOS2 server URL must start with http:// or https://.")
            request = urllib.request.Request(
                server_url + "/tts/speakers",
                headers={"X-TTS-Session-ID": self.zonos2_session_id},
                method="GET",
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))
            speakers = result.get("speakers", [])
            selected = self.zonos2_voice.currentData() or self.zonos2_voice.currentText().strip()
            self.zonos2_voice.blockSignals(True)
            self.zonos2_voice.clear()
            self.zonos2_voice.addItem("Server default / no voice", "")
            for speaker in speakers:
                speaker_id = str(speaker.get("speaker_id", "")).strip()
                if not speaker_id:
                    continue
                label = str(speaker.get("label") or speaker_id)
                self.zonos2_voice.addItem(label, speaker_id)
            local_count = self.add_local_zonos2_profiles()
            index = self.zonos2_voice.findData(selected)
            self.zonos2_voice.setCurrentIndex(index if index >= 0 else 0)
            self.zonos2_voice.blockSignals(False)
            self.zonos2_status.setText(
                f"Loaded {len(speakers)} server voice(s) and {local_count} local clone(s)."
            )
            self.append_zonos2_log(self.zonos2_status.text())
        except urllib.error.URLError:
            message = zonos2_connection_error(self.zonos2_server_url.text().strip().rstrip("/"))
            self.zonos2_status.setText("ZONOS2 server is not running.")
            self.append_zonos2_log(message)
            QMessageBox.warning(self, "ZONOS2 server unavailable", message)
        except Exception as exc:
            QMessageBox.warning(self, "Cannot load ZONOS2 voices", str(exc))

    def verify_zonos2_server(self, server_url: str) -> None:
        request = urllib.request.Request(
            server_url.rstrip("/") + "/tts/speakers",
            headers={"X-TTS-Session-ID": self.zonos2_session_id},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=10):
                return
        except urllib.error.URLError as exc:
            raise RuntimeError(zonos2_connection_error(server_url)) from exc

    def append_zonos2_log(self, message: str) -> None:
        log_event("UI | " + message)
        self.zonos2_log.appendPlainText(message)
        scrollbar = self.zonos2_log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def pick_zonos2_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "ZONOS2 output folder")
        if path:
            self.active_zonos2_output_dir = None
            self.zonos2_output_dir.setText(path)
            self.refresh_zonos2_segment_table()

    def refresh_zonos2_range(self) -> None:
        path = Path(self.zonos2_input_file.text())
        if not path.is_file():
            return
        try:
            total = len(parse_input(path))
        except Exception:
            return
        self.zonos2_range_from.setRange(1, total)
        self.zonos2_range_to.setRange(1, total)
        self.zonos2_range_to.setValue(total)

    def refresh_zonos2_segment_table(self) -> None:
        path = Path(self.zonos2_input_file.text())
        if not path.is_file():
            self.zonos2_segment_table.setRowCount(0)
            return
        try:
            segments = parse_input(path)
        except Exception:
            self.zonos2_segment_table.setRowCount(0)
            return
        total = len(segments)
        width = max(3, len(str(total)))
        output_dir = self.current_zonos2_session_dir()
        extension = self.zonos2_output_format.currentText()
        self.zonos2_segment_table.setRowCount(total)
        for row, segment in enumerate(segments):
            position = row + 1
            audio_path = output_dir / f"{position:0{width}d}.{extension}" if output_dir else None
            completed = bool(audio_path and audio_path.is_file() and audio_path.stat().st_size > 0)
            time_text = ""
            if segment.start_seconds is not None:
                time_text = f"{segment.start_seconds:.2f}-{segment.end_seconds:.2f}"
            self.zonos2_segment_table.setItem(row, 0, QTableWidgetItem(str(position)))
            self.zonos2_segment_table.setItem(row, 1, QTableWidgetItem(time_text))
            self.zonos2_segment_table.setItem(row, 2, QTableWidgetItem(segment.text))
            self.zonos2_segment_table.setItem(
                row, 3, QTableWidgetItem("Completed" if completed else "Pending")
            )
            actions = QWidget()
            action_layout = QHBoxLayout(actions)
            action_layout.setContentsMargins(0, 0, 0, 0)
            action_layout.setSpacing(3)
            play = self.icon_button(
                QStyle.StandardPixmap.SP_MediaPlay,
                "Play",
                lambda checked=False, p=position: self.play_zonos2_segment(p),
            )
            rerun = self.icon_button(
                QStyle.StandardPixmap.SP_BrowserReload,
                "Rerun and overwrite",
                lambda checked=False, p=position: self.rerun_zonos2_segment(p),
            )
            delete = self.icon_button(
                QStyle.StandardPixmap.SP_TrashIcon,
                "Delete audio file",
                lambda checked=False, p=position: self.delete_zonos2_segment(p),
            )
            play.setEnabled(completed)
            delete.setEnabled(completed)
            action_layout.addWidget(play)
            action_layout.addWidget(rerun)
            action_layout.addWidget(delete)
            self.zonos2_segment_table.setCellWidget(row, 4, actions)

    def zonos2_segment_audio_path(self, position: int) -> Path:
        total = max(1, self.zonos2_segment_table.rowCount())
        width = max(3, len(str(total)))
        directory = self.active_zonos2_output_dir or Path(self.zonos2_output_dir.text())
        return directory / f"{position:0{width}d}.{self.zonos2_output_format.currentText()}"

    def play_zonos2_segment(self, position: int) -> None:
        path = self.zonos2_segment_audio_path(position)
        if path.is_file():
            os.startfile(path)

    def rerun_zonos2_segment(self, position: int) -> None:
        self.start_zonos2(start_override=position, end_override=position, overwrite_override=True)

    def delete_zonos2_segment(self, position: int) -> None:
        path = self.zonos2_segment_audio_path(position)
        if path.is_file():
            path.unlink()
        self.refresh_zonos2_segment_table()

    def current_zonos2_session_dir(self, create: bool = False) -> Path | None:
        root_text = self.zonos2_output_dir.text().strip()
        if not root_text:
            return None
        root = Path(root_text)
        if self.active_zonos2_output_dir and self.active_zonos2_output_dir.parent == root:
            return self.active_zonos2_output_dir
        if create:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.active_zonos2_output_dir = root / f"zonos2_{timestamp}"
            suffix = 2
            while self.active_zonos2_output_dir.exists():
                self.active_zonos2_output_dir = root / f"zonos2_{timestamp}_{suffix:02d}"
                suffix += 1
            self.active_zonos2_output_dir.mkdir(parents=True, exist_ok=True)
            return self.active_zonos2_output_dir
        return None

    def copy_to_zonos2(self) -> None:
        self.zonos2_input_file.setText(self.input_file.text())
        self.zonos2_output_dir.setText(self.output_dir.text())
        self.zonos2_output_format.setCurrentText(self.output_format.currentText())
        self.zonos2_preview_count.setValue(self.preview_count.value())
        self.zonos2_cooldown_seconds.setValue(self.cooldown_seconds.value())
        self.zonos2_normalize_audio.setChecked(self.normalize_audio.isChecked())
        self.zonos2_merge_pause.setValue(self.merge_pause.value())
        language = str(self.language.currentData() or "raw")
        zonos_language = {"en": "en_us"}.get(language, "raw")
        self.zonos2_language.setCurrentIndex(max(0, self.zonos2_language.findData(zonos_language)))
        self.active_zonos2_output_dir = None
        self.refresh_zonos2_range()
        self.refresh_zonos2_segment_table()
        self.zonos2_status.setText("Copied compatible OmniVoice settings to ZONOS2.")

    def current_session_dir(self, create: bool = False) -> Path | None:
        root_text = self.output_dir.text().strip()
        if not root_text:
            return None
        root = Path(root_text)
        if self.active_output_dir and self.active_output_dir.parent == root:
            return self.active_output_dir
        if create:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.active_output_dir = root / f"voiceover_{timestamp}"
            self.active_omnivoice_profile = ""
            self.active_omnivoice_suffix = ""
            suffix = 2
            while self.active_output_dir.exists():
                self.active_output_dir = root / f"voiceover_{timestamp}_{suffix:02d}"
                suffix += 1
            self.active_output_dir.mkdir(parents=True, exist_ok=True)
            return self.active_output_dir
        return None

    def pick_cache(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Hugging Face model cache")
        if path:
            self.hf_home.setText(path)

    def refresh_segment_table(self) -> None:
        path = Path(self.input_file.text())
        if not path.is_file():
            self.segment_table.setRowCount(0)
            return
        try:
            segments = parse_input(path)
        except Exception:
            self.segment_table.setRowCount(0)
            return
        total = len(segments)
        self.range_from.setRange(1, total)
        self.range_to.setRange(1, total)
        self.range_to.setValue(total)
        width = max(3, len(str(total)))
        output_dir = self.current_session_dir()
        extension = self.output_format.currentText()
        self.segment_table.setRowCount(total)
        for row, segment in enumerate(segments):
            position = row + 1
            audio_path = (
                output_dir / f"{position:0{width}d}{self.active_omnivoice_suffix}.{extension}"
                if output_dir
                else None
            )
            completed = bool(audio_path and audio_path.is_file() and audio_path.stat().st_size > 0)
            time_text = ""
            if segment.start_seconds is not None:
                time_text = f"{segment.start_seconds:.2f}-{segment.end_seconds:.2f}"
            self.segment_table.setItem(row, 0, QTableWidgetItem(str(position)))
            self.segment_table.setItem(row, 1, QTableWidgetItem(time_text))
            self.segment_table.setItem(row, 2, QTableWidgetItem(segment.text))
            self.segment_table.setItem(row, 3, QTableWidgetItem("Completed" if completed else "Pending"))
            direction = self.segment_direction(position, segment.text)
            direction_item = QTableWidgetItem(direction or "Default voice")
            direction_item.setToolTip(direction or "No speaking direction")
            self.segment_table.setItem(row, 4, direction_item)
            actions = QWidget()
            action_layout = QHBoxLayout(actions)
            action_layout.setContentsMargins(0, 0, 0, 0)
            action_layout.setSpacing(3)
            play = self.icon_button(
                QStyle.StandardPixmap.SP_MediaPlay,
                "Play",
                lambda checked=False, p=position: self.play_segment(p),
            )
            rerun = self.icon_button(
                QStyle.StandardPixmap.SP_BrowserReload,
                "Rerun and overwrite",
                lambda checked=False, p=position: self.rerun_segment(p),
            )
            delete = self.icon_button(
                QStyle.StandardPixmap.SP_TrashIcon,
                "Delete audio file",
                lambda checked=False, p=position: self.delete_segment(p),
            )
            play.setEnabled(completed)
            delete.setEnabled(completed)
            action_layout.addWidget(play)
            action_layout.addWidget(rerun)
            action_layout.addWidget(delete)
            self.segment_table.setCellWidget(row, 5, actions)

    def segment_direction(self, position: int, text: str) -> str:
        if not self.use_speaking_style.isChecked():
            return ""
        override = self.segment_style_overrides.get(position, "").strip()
        if override:
            return normalize_omnivoice_instruct(override)
        base = self.speaking_style.currentText().strip()
        if self.style_mode.currentData() == "auto":
            return infer_speaking_direction(text, base)
        return normalize_omnivoice_instruct(base)

    def set_selected_segment_style(self) -> None:
        rows = sorted({index.row() for index in self.segment_table.selectionModel().selectedRows()})
        if not rows:
            QMessageBox.information(self, "Segment direction", "Select one or more segment rows first.")
            return
        first_position = rows[0] + 1
        current = self.segment_style_overrides.get(
            first_position, self.speaking_style.currentText().strip()
        )
        direction, accepted = QInputDialog.getText(
            self,
            "Segment direction override",
            f"Direction for {len(rows)} selected segment(s):",
            text=current,
        )
        if accepted and direction.strip():
            normalized = normalize_omnivoice_instruct(direction)
            if not normalized:
                QMessageBox.warning(
                    self,
                    "Unsupported direction",
                    "OmniVoice did not recognize any supported voice attributes. "
                    "Examples: elderly, low pitch, whisper, british accent.",
                )
                return
            for row in rows:
                self.segment_style_overrides[row + 1] = normalized
            self.refresh_segment_table()

    def clear_selected_segment_style(self) -> None:
        rows = {index.row() for index in self.segment_table.selectionModel().selectedRows()}
        for row in rows:
            self.segment_style_overrides.pop(row + 1, None)
        if rows:
            self.refresh_segment_table()

    def segment_audio_path(self, position: int) -> Path:
        total = max(1, self.segment_table.rowCount())
        width = max(3, len(str(total)))
        directory = self.active_output_dir or Path(self.output_dir.text())
        return directory / (
            f"{position:0{width}d}{self.active_omnivoice_suffix}.{self.output_format.currentText()}"
        )

    def resolve_omnivoice_voice_change(
        self,
        profile_name: str,
        output_dir: Path,
        total: int,
        start_position: int,
        end_position: int,
        overwrite_requested: bool,
    ) -> tuple[str, bool] | None:
        if not self.active_omnivoice_profile or self.active_omnivoice_profile == profile_name:
            self.active_omnivoice_profile = profile_name
            return self.active_omnivoice_suffix, overwrite_requested
        width = max(3, len(str(total)))
        existing = [
            output_dir
            / f"{position:0{width}d}{self.active_omnivoice_suffix}.{self.output_format.currentText()}"
            for position in range(start_position, end_position + 1)
        ]
        if overwrite_requested or not any(path.is_file() for path in existing):
            self.active_omnivoice_profile = profile_name
            return self.active_omnivoice_suffix, overwrite_requested

        message = QMessageBox(self)
        message.setWindowTitle("Different OmniVoice voice selected")
        message.setIcon(QMessageBox.Icon.Question)
        message.setText(
            f"Existing audio was created with '{voice_display_name(self.active_omnivoice_profile)}'.\n"
            f"You selected '{voice_display_name(profile_name)}'."
        )
        message.setInformativeText(
            "Create a new numbered variant such as 001-a, or overwrite the existing numbered files?"
        )
        create_button = message.addButton("Create new variant", QMessageBox.ButtonRole.AcceptRole)
        overwrite_button = message.addButton(
            "Overwrite existing", QMessageBox.ButtonRole.DestructiveRole
        )
        message.addButton(QMessageBox.StandardButton.Cancel)
        message.exec()
        if message.clickedButton() is create_button:
            self.active_omnivoice_suffix = next_audio_variant_suffix(
                output_dir, total, self.output_format.currentText()
            )
            self.active_omnivoice_profile = profile_name
            return self.active_omnivoice_suffix, False
        if message.clickedButton() is overwrite_button:
            self.active_omnivoice_profile = profile_name
            return self.active_omnivoice_suffix, True
        return None

    def play_segment(self, position: int) -> None:
        path = self.segment_audio_path(position)
        if path.is_file():
            os.startfile(path)

    def rerun_segment(self, position: int) -> None:
        self.start_render(start_override=position, end_override=position, overwrite_override=True)

    def delete_segment(self, position: int) -> None:
        path = self.segment_audio_path(position)
        if path.is_file():
            path.unlink()
        self.refresh_segment_table()

    def open_output_folder(self) -> None:
        path = self.current_session_dir() or Path(self.output_dir.text())
        if path.is_dir():
            os.startfile(path)
        else:
            QMessageBox.warning(self, "Output folder", "The output folder does not exist yet.")

    def save_app_settings(self) -> None:
        try:
            self.persist_settings()
            QMessageBox.information(
                self,
                "Saved",
                "Tab configurations saved locally to:\n"
                f"{tab_config_path('voice_clone')}\n"
                f"{tab_config_path('video_effect')}\n"
                f"{tab_config_path('caption')}",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Could not save settings", str(exc))

    def save_voice_clone_settings(self) -> None:
        self.save_tab_settings("voice_clone", "Voice Clone settings saved.")

    def save_moss_settings(self) -> None:
        self.save_tab_settings("voice_clone_v2", "Voice Clone v2 settings saved.")

    def load_moss_defaults(self) -> None:
        self.set_moss_checkpoint(DEFAULTS["moss_model_name"])
        self.moss_device.setCurrentIndex(max(0, self.moss_device.findData(DEFAULTS["moss_compute_device"])))
        self.moss_dtype.setCurrentIndex(max(0, self.moss_dtype.findData(DEFAULTS["moss_dtype"])))
        self.moss_attention.setCurrentIndex(max(0, self.moss_attention.findData(DEFAULTS["moss_attention"])))
        self.moss_language.setCurrentIndex(max(0, self.moss_language.findData(DEFAULTS["moss_language"])))
        self.moss_max_new_tokens.setValue(int(DEFAULTS["moss_max_new_tokens"]))
        self.moss_auto_duration.setChecked(setting_bool(DEFAULTS, "moss_auto_duration"))
        self.moss_auto_qa_retry.setChecked(setting_bool(DEFAULTS, "moss_auto_qa_retry"))
        self.moss_auto_qa_max_retries.setValue(
            setting_int(DEFAULTS, "moss_auto_qa_max_retries")
        )
        self.moss_asr_workers.setValue(setting_int(DEFAULTS, "moss_asr_workers"))
        self.moss_preview_count.setValue(int(DEFAULTS["moss_preview_count"]))
        self.moss_cooldown.setValue(int(DEFAULTS["moss_cooldown_seconds"]))
        self.moss_normalize.setChecked(setting_bool(DEFAULTS, "moss_normalize_audio"))
        self.moss_merge_pause.setValue(float(DEFAULTS["moss_merge_pause"]))
        self.moss_output_format.setCurrentText(DEFAULTS["moss_output_format"])
        self.moss_status.setText("Default MOSS-TTS settings loaded. Click Save Settings to keep them.")

    def save_video_effect_settings(self) -> None:
        self.save_tab_settings("video_effect", "Video Effect settings saved.")

    def save_environment_settings(self) -> None:
        self.save_tab_settings("environment", "Environment settings saved.")

    def save_tab_settings(self, tab_name: str, message: str) -> None:
        try:
            self.persist_settings(tab_name)
            QMessageBox.information(
                self,
                "Saved",
                f"{message}\n\nSaved to:\n{self.settings_file_for_tab(tab_name)}",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Could not save settings", str(exc))

    def settings_file_for_tab(self, tab_name: str) -> Path:
        if tab_name == "environment":
            return config_path()
        return tab_config_path(tab_name)

    def load_defaults(self) -> None:
        self.model_name.setText(DEFAULTS["model_name"])
        self.steps.setValue(int(DEFAULTS["steps"]))
        self.compute_device.setCurrentIndex(
            max(0, self.compute_device.findData(DEFAULTS["compute_device"]))
        )
        self.preview_count.setValue(int(DEFAULTS["preview_count"]))
        self.cooldown_seconds.setValue(int(DEFAULTS["cooldown_seconds"]))
        self.reload_every.setValue(int(DEFAULTS["reload_every"]))
        self.fit_timeline.setChecked(setting_bool(DEFAULTS, "fit_timeline"))
        self.output_format.setCurrentText(DEFAULTS["output_format"])
        self.merge_pause.setValue(float(DEFAULTS["merge_pause"]))
        self.normalize_audio.setChecked(setting_bool(DEFAULTS, "normalize_audio"))
        self.use_speaking_style.setChecked(setting_bool(DEFAULTS, "use_speaking_style"))
        self.speaking_style.setCurrentText(DEFAULTS["speaking_style"])
        self.style_mode.setCurrentIndex(max(0, self.style_mode.findData(DEFAULTS["style_mode"])))
        self.zonos2_server_url.setText(DEFAULTS["zonos2_server_url"])
        self.zonos2_voice.clear()
        self.zonos2_voice.addItem("Server default / no voice", "")
        self.add_local_zonos2_profiles()
        self.zonos2_voice.setCurrentIndex(0)
        self.zonos2_language.setCurrentIndex(
            max(0, self.zonos2_language.findData(DEFAULTS["zonos2_language"]))
        )
        self.zonos2_speed.setValue(float(DEFAULTS["zonos2_speed"]))
        self.zonos2_seed.setValue(int(DEFAULTS["zonos2_seed"]))
        self.zonos2_accurate_mode.setChecked(setting_bool(DEFAULTS, "zonos2_accurate_mode"))
        self.zonos2_clean_speaker_background.setChecked(
            setting_bool(DEFAULTS, "zonos2_clean_speaker_background")
        )
        self.zonos2_temperature.setValue(float(DEFAULTS["zonos2_temperature"]))
        self.zonos2_topk.setValue(int(DEFAULTS["zonos2_topk"]))
        self.zonos2_min_p.setValue(float(DEFAULTS["zonos2_min_p"]))
        self.zonos2_repetition_penalty.setValue(float(DEFAULTS["zonos2_repetition_penalty"]))
        self.zonos2_preview_count.setValue(int(DEFAULTS["zonos2_preview_count"]))
        self.zonos2_cooldown_seconds.setValue(int(DEFAULTS["zonos2_cooldown_seconds"]))
        self.zonos2_normalize_audio.setChecked(setting_bool(DEFAULTS, "zonos2_normalize_audio"))
        self.zonos2_merge_pause.setValue(float(DEFAULTS["zonos2_merge_pause"]))
        self.zonos2_output_format.setCurrentText(DEFAULTS["zonos2_output_format"])
        self.video_effect_width.setValue(int(DEFAULTS["video_effect_width"]))
        self.video_effect_height.setValue(int(DEFAULTS["video_effect_height"]))
        self.video_effect_aspect_ratio.setCurrentText(DEFAULTS["video_effect_aspect_ratio"])
        self.video_effect_quality.setCurrentText(DEFAULTS["video_effect_quality"])
        self.update_video_effect_dimensions()
        self.video_effect_fps.setValue(int(DEFAULTS["video_effect_fps"]))
        self.video_effect_crf.setValue(int(DEFAULTS["video_effect_crf"]))
        self.video_effect_codec.setCurrentText(DEFAULTS["video_effect_codec"])
        self.video_effect_workers.setValue(int(DEFAULTS["video_effect_workers"]))
        self.video_effect_pattern.setText(DEFAULTS["video_effect_pattern"])
        self.video_effect_random_effects.setChecked(setting_bool(DEFAULTS, "video_effect_random_effects"))
        self.video_effect_bounce.setChecked(setting_bool(DEFAULTS, "video_effect_bounce"))
        self.video_effect_merge.setChecked(setting_bool(DEFAULTS, "video_effect_merge"))
        self.video_effect_zoom_scale.setValue(float(DEFAULTS["video_effect_zoom_scale"]))
        self.video_effect_base_crop.setValue(float(DEFAULTS["video_effect_base_crop"]))
        self.video_effect_edge_reach.setValue(float(DEFAULTS["video_effect_edge_reach"]))
        self.video_effect_face_safe.setValue(float(DEFAULTS["video_effect_face_safe"]))
        self.video_effect_speed.setValue(float(DEFAULTS["video_effect_speed"]))
        self.video_effect_pre_silence.setValue(float(DEFAULTS["video_effect_pre_silence"]))
        self.video_effect_min_motion.setValue(float(DEFAULTS["video_effect_min_motion"]))
        self.video_effect_combo_radius.setValue(float(DEFAULTS["video_effect_combo_radius"]))
        self.video_effect_combo_offset_x.setValue(float(DEFAULTS["video_effect_combo_offset_x"]))
        self.video_effect_combo_offset_y.setValue(float(DEFAULTS["video_effect_combo_offset_y"]))
        self.refresh_video_effect_motion_templates(DEFAULTS["video_effect_motion_template"])
        self.apply_video_effect_motion_template(DEFAULTS["video_effect_motion_template"])
        self.video_effect_retro_preset.setCurrentText(DEFAULTS["video_effect_retro_preset"])
        self.video_effect_retro_scratches_enabled.setChecked(setting_bool(DEFAULTS, "video_effect_retro_scratches_enabled"))
        self.video_effect_retro_scratch.setValue(float(DEFAULTS["video_effect_retro_scratch"]))
        self.video_effect_retro_dust_enabled.setChecked(setting_bool(DEFAULTS, "video_effect_retro_dust_enabled"))
        self.video_effect_retro_dust.setValue(float(DEFAULTS["video_effect_retro_dust"]))
        self.video_effect_retro_grain_enabled.setChecked(setting_bool(DEFAULTS, "video_effect_retro_grain_enabled"))
        self.video_effect_retro_grain.setValue(float(DEFAULTS["video_effect_retro_grain"]))
        self.video_effect_retro_flicker_enabled.setChecked(setting_bool(DEFAULTS, "video_effect_retro_flicker_enabled"))
        self.video_effect_retro_flicker.setValue(float(DEFAULTS["video_effect_retro_flicker"]))
        self.video_effect_retro_vignette_enabled.setChecked(setting_bool(DEFAULTS, "video_effect_retro_vignette_enabled"))
        self.video_effect_retro_vignette.setValue(float(DEFAULTS["video_effect_retro_vignette"]))
        self.video_effect_retro_color_fade_enabled.setChecked(setting_bool(DEFAULTS, "video_effect_retro_color_fade_enabled"))
        self.video_effect_retro_color_fade.setValue(float(DEFAULTS["video_effect_retro_color_fade"]))
        self.video_effect_retro_scan_lines_enabled.setChecked(setting_bool(DEFAULTS, "video_effect_retro_scan_lines_enabled"))
        self.video_effect_retro_scan_lines.setValue(float(DEFAULTS["video_effect_retro_scan_lines"]))
        self.apply_video_effect_retro_preset()
        self.status.setText("Default Generation / Output settings loaded. Click Save to keep them.")
        self.zonos2_status.setText("Best default ZONOS2 settings loaded. Click Save Settings to keep them.")
        self.video_effect_status.setText("Default Video Effect settings loaded. Click Save Settings to keep them.")
        self.load_caption_defaults()

    def load_video_effect_defaults(self) -> None:
        self.video_effect_width.setValue(int(DEFAULTS["video_effect_width"]))
        self.video_effect_height.setValue(int(DEFAULTS["video_effect_height"]))
        self.video_effect_aspect_ratio.setCurrentText(DEFAULTS["video_effect_aspect_ratio"])
        self.video_effect_quality.setCurrentText(DEFAULTS["video_effect_quality"])
        self.update_video_effect_dimensions()
        self.video_effect_fps.setValue(int(DEFAULTS["video_effect_fps"]))
        self.video_effect_crf.setValue(int(DEFAULTS["video_effect_crf"]))
        self.video_effect_codec.setCurrentText(DEFAULTS["video_effect_codec"])
        self.video_effect_workers.setValue(int(DEFAULTS["video_effect_workers"]))
        self.video_effect_pattern.setText(DEFAULTS["video_effect_pattern"])
        self.video_effect_random_effects.setChecked(setting_bool(DEFAULTS, "video_effect_random_effects"))
        self.video_effect_bounce.setChecked(setting_bool(DEFAULTS, "video_effect_bounce"))
        self.video_effect_merge.setChecked(setting_bool(DEFAULTS, "video_effect_merge"))
        self.video_effect_zoom_scale.setValue(float(DEFAULTS["video_effect_zoom_scale"]))
        self.video_effect_base_crop.setValue(float(DEFAULTS["video_effect_base_crop"]))
        self.video_effect_edge_reach.setValue(float(DEFAULTS["video_effect_edge_reach"]))
        self.video_effect_face_safe.setValue(float(DEFAULTS["video_effect_face_safe"]))
        self.video_effect_speed.setValue(float(DEFAULTS["video_effect_speed"]))
        self.video_effect_pre_silence.setValue(float(DEFAULTS["video_effect_pre_silence"]))
        self.video_effect_min_motion.setValue(float(DEFAULTS["video_effect_min_motion"]))
        self.video_effect_combo_radius.setValue(float(DEFAULTS["video_effect_combo_radius"]))
        self.video_effect_combo_offset_x.setValue(float(DEFAULTS["video_effect_combo_offset_x"]))
        self.video_effect_combo_offset_y.setValue(float(DEFAULTS["video_effect_combo_offset_y"]))
        self.refresh_video_effect_motion_templates(DEFAULTS["video_effect_motion_template"])
        self.apply_video_effect_motion_template(DEFAULTS["video_effect_motion_template"])
        self.video_effect_retro_preset.setCurrentText(DEFAULTS["video_effect_retro_preset"])
        self.video_effect_retro_scratches_enabled.setChecked(setting_bool(DEFAULTS, "video_effect_retro_scratches_enabled"))
        self.video_effect_retro_scratch.setValue(float(DEFAULTS["video_effect_retro_scratch"]))
        self.video_effect_retro_dust_enabled.setChecked(setting_bool(DEFAULTS, "video_effect_retro_dust_enabled"))
        self.video_effect_retro_dust.setValue(float(DEFAULTS["video_effect_retro_dust"]))
        self.video_effect_retro_grain_enabled.setChecked(setting_bool(DEFAULTS, "video_effect_retro_grain_enabled"))
        self.video_effect_retro_grain.setValue(float(DEFAULTS["video_effect_retro_grain"]))
        self.video_effect_retro_flicker_enabled.setChecked(setting_bool(DEFAULTS, "video_effect_retro_flicker_enabled"))
        self.video_effect_retro_flicker.setValue(float(DEFAULTS["video_effect_retro_flicker"]))
        self.video_effect_retro_vignette_enabled.setChecked(setting_bool(DEFAULTS, "video_effect_retro_vignette_enabled"))
        self.video_effect_retro_vignette.setValue(float(DEFAULTS["video_effect_retro_vignette"]))
        self.video_effect_retro_color_fade_enabled.setChecked(setting_bool(DEFAULTS, "video_effect_retro_color_fade_enabled"))
        self.video_effect_retro_color_fade.setValue(float(DEFAULTS["video_effect_retro_color_fade"]))
        self.video_effect_retro_scan_lines_enabled.setChecked(setting_bool(DEFAULTS, "video_effect_retro_scan_lines_enabled"))
        self.video_effect_retro_scan_lines.setValue(float(DEFAULTS["video_effect_retro_scan_lines"]))
        self.apply_video_effect_retro_preset()
        self.video_effect_status.setText("Default Video Effect settings loaded. Click Save Settings to keep them.")
        self.video_effect_log_message(self.video_effect_status.text())

    def load_caption_defaults(self) -> None:
        self.caption_video_file.setText(DEFAULTS["caption_video_file"])
        self.caption_import_file.setText(DEFAULTS["caption_import_file"])
        self.caption_output_dir.setText(DEFAULTS["caption_output_dir"])
        self.caption_mode.setCurrentText(DEFAULTS["caption_mode"])
        self.caption_engine.setCurrentText(DEFAULTS["caption_engine"])
        self.caption_render_engine.setCurrentText(DEFAULTS["caption_render_engine"])
        self.caption_device.setCurrentText(DEFAULTS["caption_device"])
        self.caption_word_timing.setChecked(setting_bool(DEFAULTS, "caption_word_timing"))
        self.caption_language.setCurrentText(DEFAULTS["caption_language"])
        self.caption_model.setCurrentText(DEFAULTS["caption_model"])
        self.caption_accuracy.setCurrentText(DEFAULTS["caption_accuracy"])
        self.caption_speed_preset.setCurrentText(DEFAULTS["caption_speed_preset"])
        self.caption_transcribe_batch.setValue(setting_int(DEFAULTS, "caption_transcribe_batch"))
        self.caption_workers.setValue(setting_int(DEFAULTS, "caption_workers"))
        self.caption_preset.setCurrentText(DEFAULTS["caption_preset"])
        self.caption_burn_video.setChecked(setting_bool(DEFAULTS, "caption_burn_video"))
        self.apply_caption_preset(DEFAULTS["caption_preset"])
        self.caption_status.setText("Default Caption settings loaded. Click Save Settings to keep them.")

    def open_log_folder(self) -> None:
        os.startfile(log_dir())

    def current_settings_payload(self) -> dict[str, str]:
        return {
                "ui_language": self.ui_language,
                "hf_token": self.hf_token.text(),
                "gemini_api_key": self.gemini_key.text(),
                "hf_home": self.hf_home.text(),
                "merge_pause": str(self.merge_pause.value()),
                "model_name": self.model_name.text(),
                "steps": str(self.steps.value()),
                "compute_device": str(self.compute_device.currentData()),
                "preview_count": str(self.preview_count.value()),
                "cooldown_seconds": str(self.cooldown_seconds.value()),
                "reload_every": str(self.reload_every.value()),
                "fit_timeline": str(self.fit_timeline.isChecked()).lower(),
                "normalize_audio": str(self.normalize_audio.isChecked()).lower(),
                "output_format": self.output_format.currentText(),
                "output_dir": self.output_dir.text(),
                "language": str(self.language.currentData() or ""),
                "default_voice_profile": self.default_voice_profile_name,
                "speaking_style": self.speaking_style.currentText(),
                "style_mode": str(self.style_mode.currentData()),
                "use_speaking_style": str(self.use_speaking_style.isChecked()).lower(),
                "automation_voice_engine": str(
                    self.automation_voice_engine.currentData() or "original"
                ),
                "moss_model_name": self.selected_moss_checkpoint(),
                "moss_compute_device": str(self.moss_device.currentData()),
                "moss_dtype": str(self.moss_dtype.currentData()),
                "moss_attention": str(self.moss_attention.currentData()),
                "moss_language": str(self.moss_language.currentData()),
                "moss_max_new_tokens": str(self.moss_max_new_tokens.value()),
                "moss_auto_duration": str(self.moss_auto_duration.isChecked()).lower(),
                "moss_auto_qa_retry": str(self.moss_auto_qa_retry.isChecked()).lower(),
                "moss_auto_qa_max_retries": str(self.moss_auto_qa_max_retries.value()),
                "moss_asr_workers": str(self.moss_asr_workers.value()),
                "moss_preview_count": str(self.moss_preview_count.value()),
                "moss_cooldown_seconds": str(self.moss_cooldown.value()),
                "moss_normalize_audio": str(self.moss_normalize.isChecked()).lower(),
                "moss_merge_pause": str(self.moss_merge_pause.value()),
                "moss_output_format": self.moss_output_format.currentText(),
                "moss_input_file": self.moss_input_file.text(),
                "moss_output_dir": self.moss_output_dir.text(),
                "moss_last_session_dir": str(self.active_moss_output_dir or ""),
                "zonos2_server_url": self.zonos2_server_url.text(),
                "zonos2_voice_id": str(
                    self.zonos2_voice.currentData() or self.zonos2_voice.currentText()
                ),
                "zonos2_language": str(self.zonos2_language.currentData()),
                "zonos2_speed": str(self.zonos2_speed.value()),
                "zonos2_seed": str(self.zonos2_seed.value()),
                "zonos2_accurate_mode": str(self.zonos2_accurate_mode.isChecked()).lower(),
                "zonos2_clean_speaker_background": str(
                    self.zonos2_clean_speaker_background.isChecked()
                ).lower(),
                "zonos2_temperature": str(self.zonos2_temperature.value()),
                "zonos2_topk": str(self.zonos2_topk.value()),
                "zonos2_min_p": str(self.zonos2_min_p.value()),
                "zonos2_repetition_penalty": str(self.zonos2_repetition_penalty.value()),
                "zonos2_preview_count": str(self.zonos2_preview_count.value()),
                "zonos2_cooldown_seconds": str(self.zonos2_cooldown_seconds.value()),
                "zonos2_normalize_audio": str(self.zonos2_normalize_audio.isChecked()).lower(),
                "zonos2_merge_pause": str(self.zonos2_merge_pause.value()),
                "zonos2_output_format": self.zonos2_output_format.currentText(),
                "zonos2_output_dir": self.zonos2_output_dir.text(),
                "video_effect_images_dir": self.video_effect_images_dir.text(),
                "video_effect_audios_dir": self.video_effect_audios_dir.text(),
                "video_effect_output_dir": self.video_effect_output_dir.text(),
                "video_effect_aspect_ratio": self.video_effect_aspect_ratio.currentText(),
                "video_effect_quality": self.video_effect_quality.currentText(),
                "video_effect_width": str(self.video_effect_width.value()),
                "video_effect_height": str(self.video_effect_height.value()),
                "video_effect_fps": str(self.video_effect_fps.value()),
                "video_effect_crf": str(self.video_effect_crf.value()),
                "video_effect_codec": self.video_effect_codec.currentText(),
                "video_effect_workers": str(self.video_effect_workers.value()),
                "video_effect_pattern": self.video_effect_pattern.text(),
                "video_effect_random_effects": str(self.video_effect_random_effects.isChecked()).lower(),
                "video_effect_bounce": str(self.video_effect_bounce.isChecked()).lower(),
                "video_effect_zoom_scale": str(self.video_effect_zoom_scale.value()),
                "video_effect_base_crop": str(self.video_effect_base_crop.value()),
                "video_effect_edge_reach": str(self.video_effect_edge_reach.value()),
                "video_effect_face_safe": str(self.video_effect_face_safe.value()),
                "video_effect_speed": str(self.video_effect_speed.value()),
                "video_effect_pre_silence": str(self.video_effect_pre_silence.value()),
                "video_effect_min_motion": str(self.video_effect_min_motion.value()),
                "video_effect_combo_radius": str(self.video_effect_combo_radius.value()),
                "video_effect_combo_offset_x": str(self.video_effect_combo_offset_x.value()),
                "video_effect_combo_offset_y": str(self.video_effect_combo_offset_y.value()),
                "video_effect_motion_template": self.video_effect_motion_template.currentText(),
                "video_effect_motion_templates": json.dumps(
                    self.video_effect_motion_templates, ensure_ascii=False, sort_keys=True
                ),
                "video_effect_retro_preset": self.video_effect_retro_preset.currentText(),
                "video_effect_retro_scratches_enabled": str(self.video_effect_retro_scratches_enabled.isChecked()).lower(),
                "video_effect_retro_scratch": str(self.video_effect_retro_scratch.value()),
                "video_effect_retro_dust_enabled": str(self.video_effect_retro_dust_enabled.isChecked()).lower(),
                "video_effect_retro_dust": str(self.video_effect_retro_dust.value()),
                "video_effect_retro_grain_enabled": str(self.video_effect_retro_grain_enabled.isChecked()).lower(),
                "video_effect_retro_grain": str(self.video_effect_retro_grain.value()),
                "video_effect_retro_flicker_enabled": str(self.video_effect_retro_flicker_enabled.isChecked()).lower(),
                "video_effect_retro_flicker": str(self.video_effect_retro_flicker.value()),
                "video_effect_retro_vignette_enabled": str(self.video_effect_retro_vignette_enabled.isChecked()).lower(),
                "video_effect_retro_vignette": str(self.video_effect_retro_vignette.value()),
                "video_effect_retro_color_fade_enabled": str(self.video_effect_retro_color_fade_enabled.isChecked()).lower(),
                "video_effect_retro_color_fade": str(self.video_effect_retro_color_fade.value()),
                "video_effect_retro_scan_lines_enabled": str(self.video_effect_retro_scan_lines_enabled.isChecked()).lower(),
                "video_effect_retro_scan_lines": str(self.video_effect_retro_scan_lines.value()),
                "video_effect_merge": str(self.video_effect_merge.isChecked()).lower(),
                "caption_video_file": self.caption_video_file.text(),
                "caption_import_file": self.caption_import_file.text(),
                "caption_output_dir": self.caption_output_dir.text(),
                "caption_mode": self.caption_mode.currentText(),
                "caption_engine": self.caption_engine.currentText(),
                "caption_render_engine": self.caption_render_engine.currentText(),
                "caption_device": self.caption_device.currentText(),
                "caption_word_timing": str(self.caption_word_timing.isChecked()).lower(),
                "caption_language": self.caption_language.currentText(),
                "caption_model": self.caption_model.currentText(),
                "caption_accuracy": self.caption_accuracy.currentText(),
                "caption_speed_preset": self.caption_speed_preset.currentText(),
                "caption_transcribe_batch": str(self.caption_transcribe_batch.value()),
                "caption_workers": str(self.caption_workers.value()),
                "caption_preset": self.caption_preset.currentText(),
                "caption_burn_video": str(self.caption_burn_video.isChecked()).lower(),
                "caption_youtube_auto": str(self.caption_youtube_auto.isChecked()).lower(),
                "caption_config_json": json.dumps(
                    self.caption_config(), ensure_ascii=False, separators=(",", ":")
                ),
                "watermark_input_files": "\n".join(self.watermark_input_paths()),
                "watermark_output_dir": self.watermark_output_dir.text(),
                "watermark_names": self.watermark_names.toPlainText(),
                "watermark_trailer_video": self.watermark_trailer_video.text(),
                "watermark_transition_duration": str(self.watermark_transition_duration.value()),
                "watermark_position": self.watermark_position.currentText(),
                "watermark_name_start": str(self.watermark_name_start.value()),
                "watermark_padding_x": str(self.watermark_padding_x.value()),
                "watermark_padding_y": str(self.watermark_padding_y.value()),
                "watermark_font": self.watermark_font.currentText(),
                "watermark_font_size": str(self.watermark_font_size.value()),
                "watermark_bold": str(self.watermark_bold.isChecked()).lower(),
                "watermark_italic": str(self.watermark_italic.isChecked()).lower(),
                "watermark_text_color": self.watermark_text_color.text(),
                "watermark_background": self.watermark_background.currentText(),
                "watermark_background_color": self.watermark_background_color.text(),
                "watermark_background_opacity": str(self.watermark_background_opacity.value()),
                "watermark_warning_image": self.watermark_warning_image.text(),
                "watermark_warning_duration": str(self.watermark_warning_duration.value()),
                "watermark_warning_fit": self.watermark_warning_fit.currentText(),
                "watermark_subscribe_video": self.watermark_subscribe_video.text(),
                "watermark_subscribe_start": str(self.watermark_subscribe_start.value()),
                "watermark_subscribe_interval": str(self.watermark_subscribe_interval.value()),
                "watermark_subscribe_count": str(self.watermark_subscribe_count.value()),
                "watermark_subscribe_position": self.watermark_subscribe_position.currentText(),
                "watermark_subscribe_scale": str(self.watermark_subscribe_scale.value()),
                "watermark_chroma_key": str(self.watermark_chroma_key.isChecked()).lower(),
                "watermark_chroma_color": self.watermark_chroma_color.text(),
                "watermark_chroma_similarity": str(self.watermark_chroma_similarity.value()),
                "watermark_chroma_blend": str(self.watermark_chroma_blend.value()),
                "watermark_codec": self.watermark_codec.currentText(),
                "watermark_crf": str(self.watermark_crf.value()),
                "watermark_automation_channel_catalog": json.dumps(
                    self.automation_channel_names(), ensure_ascii=False
                ),
                "watermark_config_json": json.dumps(
                    self.watermark_config(), ensure_ascii=False, separators=(",", ":")
                ),
        }

    def persist_settings(self, tab_name: str | None = None) -> None:
        payload = self.current_settings_payload()
        if tab_name:
            save_tab_settings(tab_name, payload)
        else:
            save_settings(payload)
        self.settings.update(payload)

    def save_profile(self) -> None:
        try:
            if self.thread and self.thread.isRunning():
                raise RuntimeError("Another task is already running.")
            self.active_task_ui = "voice_list"
            self.persist_settings("voice_clone")
            name = self.profile_name.text().strip()
            selected_name = str(self.profile.currentData() or "")
            transcript = self.reference_text.toPlainText()
            if not name and selected_name:
                answer = QMessageBox.question(
                    self,
                    "Overwrite voice transcript",
                    f"Overwrite the transcript for voice profile "
                    f"'{voice_display_name(selected_name)}'?\n\n"
                    "The saved reference audio will not be changed.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    return
                profile = self.store.update_transcript(selected_name, transcript)
                self.reference_text.setPlainText(profile["reference_text"])
                message = (
                    f"Transcript updated for voice profile "
                    f"'{voice_display_name(selected_name)}'."
                )
                self.voice_list_status.setText(message)
                self.append_log(message)
                QMessageBox.information(self, "Transcript updated", message)
                return
            source_audio = Path(self.reference_audio.text())
            if not name:
                raise ValueError(
                    "Enter a new profile name, or select a saved voice to update its transcript."
                )
            if not source_audio.is_file():
                raise ValueError("Reference audio file does not exist.")

            self.worker = ProfileWorker(
                self.store,
                name,
                source_audio,
                transcript,
                self.clone_language.currentData(),
            )
            self.thread = QThread()
            self.worker.moveToThread(self.thread)
            self.thread.started.connect(self.worker.run)
            self.worker.progress.connect(self.on_profile_progress)
            self.worker.completed.connect(self.on_profile_completed)
            self.worker.failed.connect(self.on_profile_failed)
            self.worker.completed.connect(self.thread.quit)
            self.worker.failed.connect(self.thread.quit)
            self.thread.finished.connect(self.on_task_finished)
            self.set_busy(True, "Preparing voice profile...")
            self.append_log(
                "Creating voice profile. If no transcript was supplied, small.en will be "
                "downloaded automatically and cached by Hugging Face."
            )
            self.thread.start()
        except Exception as exc:
            QMessageBox.critical(self, "Could not save profile", str(exc))

    def import_piper_profiles(self) -> None:
        try:
            if self.thread and self.thread.isRunning():
                raise RuntimeError("Another task is already running.")
            self.active_task_ui = "voice_list"
            self.worker = PiperProfileWorker(self.store)
            self.thread = QThread()
            self.worker.moveToThread(self.thread)
            self.thread.started.connect(self.worker.run)
            self.worker.progress.connect(self.on_profile_progress)
            self.worker.completed.connect(self.on_piper_profiles_completed)
            self.worker.failed.connect(self.on_profile_failed)
            self.worker.completed.connect(self.thread.quit)
            self.worker.failed.connect(self.thread.quit)
            self.thread.finished.connect(self.on_task_finished)
            self.set_busy(True, "Creating complete 9-11 second clone references from ONNX voices...")
            self.append_log("Converting valid tts-model ONNX voices into reusable clone profiles.")
            self.thread.start()
        except Exception as exc:
            QMessageBox.critical(self, "Could not import ONNX voices", str(exc))

    def on_piper_profiles_completed(self, created: int, skipped: list[str]) -> None:
        self.refresh_profiles()
        message = f"Created {created} clone voice profile(s) from tts-model."
        if skipped:
            message += " Skipped missing/failed models: " + ", ".join(skipped)
        self.voice_list_status.setText(message)
        self.append_log(message)
        QMessageBox.information(self, "ONNX voices imported", message)

    def on_profile_progress(self, message: str) -> None:
        self.voice_list_status.setText(message)
        self.append_log(message)

    def on_profile_completed(self, profile: dict) -> None:
        self.refresh_profiles(profile["name"])
        self.reference_text.setPlainText(profile.get("reference_text", ""))
        self.profile_name.clear()
        self.voice_list_status.setText(f"Voice profile '{profile['name']}' saved.")
        self.append_log(self.voice_list_status.text())
        QMessageBox.information(self, "Saved", self.voice_list_status.text())

    def on_profile_failed(self, details: str) -> None:
        self.voice_list_status.setText("Could not save voice profile.")
        self.append_log(details)
        QMessageBox.critical(self, "Could not save profile", details[-4000:])

    def append_log(self, message: str) -> None:
        log_event("UI | " + message)
        if self.is_batch_running and self.current_rendering_file_name:
            prefix = f"[{self.current_rendering_file_name}] "
            if not message.startswith(prefix):
                display_message = prefix + message
            else:
                display_message = message
        else:
            display_message = message
        if self.active_task_ui == "zonos2":
            log_widget = self.zonos2_log
        elif self.active_task_ui == "voice_list":
            log_widget = self.voice_list_log
        elif self.active_task_ui == "moss":
            log_widget = self.moss_log
        elif self.active_task_ui == "video_effect":
            log_widget = self.video_effect_log
        else:
            log_widget = self.log
        log_widget.appendPlainText(display_message)
        scrollbar = log_widget.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def task_progress_widgets(self) -> tuple[QProgressBar, QLabel]:
        if self.active_task_ui == "zonos2":
            return self.zonos2_progress, self.zonos2_status
        if self.active_task_ui == "voice_list":
            return self.voice_list_progress, self.voice_list_status
        if self.active_task_ui == "moss":
            return self.moss_progress, self.moss_status
        if self.active_task_ui == "video_effect":
            return self.video_effect_progress, self.video_effect_status
        return self.progress, self.status

    def set_busy(self, busy: bool, status: str = "") -> None:
        # Keep controls available while a background task is running. Individual
        # workflows still guard against starting an incompatible duplicate job.
        self.stop_button.setEnabled(busy and isinstance(self.worker, RenderWorker))
        self.moss_stop_button.setEnabled(
            busy and (
                isinstance(self.worker, MossTTSWorker)
                or self.moss_qa_worker is not None
            )
        )
        self.zonos2_stop_button.setEnabled(busy and isinstance(self.worker, Zonos2Worker))
        self.video_effect_stop_button.setEnabled(busy and isinstance(self.worker, VideoEffectWorker))
        self.watermark_stop_button.setEnabled(busy and self.watermark_worker is not None)
        self.caption_stop_button.setEnabled(
            busy and (self.caption_process is not None or self.caption_transcribe_job is not None)
        )
        self.automation_stop_button.setEnabled(busy and self.automation_worker is not None)
        progress, status_label = self.task_progress_widgets()
        if busy:
            progress.setRange(0, 0)
        else:
            progress.setRange(0, 100)
            progress.setValue(0)
        if status:
            status_label.setText(status)

    def on_task_finished(self) -> None:
        self.set_busy(False)
        self.worker = None
        self.thread = None

    def render(self) -> None:
        valid_rows = [row for row in self.batch_rows if row["input_edit"].text().strip()]
        if len(valid_rows) > 1:
            self.start_render(batch_queue=valid_rows)
        else:
            total = max(1, self.segment_table.rowCount())
            self.start_render(start_override=1, end_override=total)

    def render_range(self) -> None:
        self.start_render(
            start_override=self.range_from.value(),
            end_override=self.range_to.value(),
            overwrite_override=self.overwrite_existing.isChecked(),
        )

    def render_preview(self) -> None:
        self.start_render(self.preview_count.value())

    def stop_current_render(self) -> None:
        cancellable_render = isinstance(
            self.worker,
            (RenderWorker, MossTTSWorker, MossAudioCheckWorker, Zonos2Worker, VideoEffectWorker),
        )
        qa_running = self.moss_qa_worker is not None
        if cancellable_render or qa_running:
            if isinstance(self.worker, VideoEffectWorker):
                self.video_effect_batch_stopping = True
            if cancellable_render:
                self.worker.request_cancel()
            if self.moss_qa_worker is not None:
                self.moss_qa_worker.request_cancel()
                self.moss_pipeline_cancelled = True
            self.stop_button.setEnabled(False)
            self.zonos2_stop_button.setEnabled(False)
            self.moss_stop_button.setEnabled(False)
            self.video_effect_stop_button.setEnabled(False)
            message = "Stop requested. Waiting for the current model operation/segment to finish safely..."
            _, status_label = self.task_progress_widgets()
            status_label.setText(message)
            self.append_log(message)

    def render_zonos2_preview(self) -> None:
        self.start_zonos2(segment_limit=self.zonos2_preview_count.value())

    def render_zonos2_range(self) -> None:
        self.start_zonos2(
            start_override=self.zonos2_range_from.value(),
            end_override=self.zonos2_range_to.value(),
            overwrite_override=self.zonos2_overwrite_existing.isChecked(),
        )

    def open_zonos2_output_folder(self) -> None:
        path = self.current_zonos2_session_dir() or Path(self.zonos2_output_dir.text())
        if path.is_dir():
            os.startfile(path)
        else:
            QMessageBox.warning(self, "ZONOS2 output folder", "The output folder does not exist yet.")

    def video_effect_dimensions_for_selection(self) -> tuple[int, int]:
        ratio_text = self.video_effect_aspect_ratio.currentText() or "16:9"
        quality = self.video_effect_quality.currentText() or "FHD"
        ratio_width, ratio_height = (int(part) for part in ratio_text.split(":", 1))
        short_edge = VIDEO_QUALITY_PRESETS.get(quality, 1080)
        if ratio_width >= ratio_height:
            height = short_edge
            width = int(round(height * ratio_width / ratio_height))
        else:
            width = short_edge
            height = int(round(width * ratio_height / ratio_width))
        width += width % 2
        height += height % 2
        return width, height

    def update_video_effect_dimensions(self) -> None:
        width, height = self.video_effect_dimensions_for_selection()
        self.video_effect_width.setValue(width)
        self.video_effect_height.setValue(height)
        self.video_effect_status.setText(
            f"Render frame: {self.video_effect_aspect_ratio.currentText()} "
            f"{self.video_effect_quality.currentText()} = {width}x{height}"
        )

    def built_in_video_effect_motion_templates(self) -> dict[str, dict]:
        return {
            "Basic Motion": {
                "pattern": "pan_lr,pan_ud,zoom_in,zoom_out,combo",
                "random_effects": True,
                "bounce": True,
                "zoom_scale": 0.02,
                "base_crop": 0.02,
                "edge_reach": 0.66,
                "face_safe": 1.8,
                "speed": 0.85,
                "min_motion": 0.018,
                "combo_radius": 0.14,
                "combo_offset_x": 0.18,
                "combo_offset_y": -0.12,
            },
            "Hard Motion": {
                "pattern": "pan_lr,pan_ud,zoom_in,zoom_out,combo",
                "random_effects": True,
                "bounce": True,
                "zoom_scale": 0.35,
                "base_crop": 0.20,
                "edge_reach": 1.0,
                "face_safe": 0.8,
                "speed": 1.15,
                "min_motion": 0.025,
                "combo_radius": 1.0,
                "combo_offset_x": 0.0,
                "combo_offset_y": 0.0,
            },
        }

    def refresh_video_effect_motion_templates(self, selected: str = "") -> None:
        combo = self.video_effect_motion_template
        previous = combo.blockSignals(True)
        combo.clear()
        combo.addItems(["Basic Motion", "Hard Motion"])
        combo.addItems(sorted(self.video_effect_motion_templates, key=str.casefold))
        combo.addItem("Custom (unsaved)")
        combo.setCurrentText(selected if combo.findText(selected) >= 0 else "Basic Motion")
        combo.blockSignals(previous)

    def current_video_effect_motion_values(self) -> dict:
        return {
            "pattern": self.video_effect_pattern.text().strip(),
            "random_effects": self.video_effect_random_effects.isChecked(),
            "bounce": self.video_effect_bounce.isChecked(),
            "zoom_scale": self.video_effect_zoom_scale.value(),
            "base_crop": self.video_effect_base_crop.value(),
            "edge_reach": self.video_effect_edge_reach.value(),
            "face_safe": self.video_effect_face_safe.value(),
            "speed": self.video_effect_speed.value(),
            "min_motion": self.video_effect_min_motion.value(),
            "combo_radius": self.video_effect_combo_radius.value(),
            "combo_offset_x": self.video_effect_combo_offset_x.value(),
            "combo_offset_y": self.video_effect_combo_offset_y.value(),
        }

    def apply_video_effect_motion_template(self, name: str) -> None:
        if name == "Custom (unsaved)":
            return
        values = self.built_in_video_effect_motion_templates().get(name)
        if values is None:
            values = self.video_effect_motion_templates.get(name)
        if not isinstance(values, dict):
            return
        self._applying_video_effect_motion_template = True
        try:
            self.video_effect_pattern.setText(str(values.get("pattern", "")))
            self.video_effect_random_effects.setChecked(bool(values.get("random_effects", True)))
            self.video_effect_bounce.setChecked(bool(values.get("bounce", True)))
            for widget, key in (
                (self.video_effect_zoom_scale, "zoom_scale"),
                (self.video_effect_base_crop, "base_crop"),
                (self.video_effect_edge_reach, "edge_reach"),
                (self.video_effect_face_safe, "face_safe"),
                (self.video_effect_speed, "speed"),
                (self.video_effect_min_motion, "min_motion"),
                (self.video_effect_combo_radius, "combo_radius"),
                (self.video_effect_combo_offset_x, "combo_offset_x"),
                (self.video_effect_combo_offset_y, "combo_offset_y"),
            ):
                if key in values:
                    widget.setValue(float(values[key]))
        finally:
            self._applying_video_effect_motion_template = False
        if hasattr(self, "video_effect_status"):
            self.video_effect_status.setText(f"Motion template loaded: {name}")

    def mark_video_effect_motion_custom(self) -> None:
        if getattr(self, "_applying_video_effect_motion_template", False):
            return
        if self.video_effect_motion_template.currentText() == "Custom (unsaved)":
            return
        previous = self.video_effect_motion_template.blockSignals(True)
        self.video_effect_motion_template.setCurrentText("Custom (unsaved)")
        self.video_effect_motion_template.blockSignals(previous)

    def save_video_effect_motion_template(self) -> None:
        name, accepted = QInputDialog.getText(
            self, "Save Motion Template", "Template name:"
        )
        name = name.strip()
        if not accepted or not name:
            return
        if name.casefold() in {"basic motion", "hard motion", "custom (unsaved)"}:
            QMessageBox.warning(
                self, "Save Motion Template", "Choose a different name for a custom template."
            )
            return
        existing_name = next(
            (item for item in self.video_effect_motion_templates if item.casefold() == name.casefold()),
            None,
        )
        if existing_name and existing_name != name:
            del self.video_effect_motion_templates[existing_name]
        self.video_effect_motion_templates[name] = self.current_video_effect_motion_values()
        self.refresh_video_effect_motion_templates(name)
        self.persist_settings("video_effect")
        self.video_effect_status.setText(f"Motion template saved: {name}")

    def delete_video_effect_motion_template(self) -> None:
        name = self.video_effect_motion_template.currentText()
        if name not in self.video_effect_motion_templates:
            QMessageBox.information(
                self, "Delete Motion Template", "Only custom motion templates can be deleted."
            )
            return
        del self.video_effect_motion_templates[name]
        self.refresh_video_effect_motion_templates("Basic Motion")
        self.apply_video_effect_motion_template("Basic Motion")
        self.persist_settings("video_effect")
        self.video_effect_status.setText(f"Motion template deleted: {name}")

    def apply_video_effect_retro_preset(self) -> None:
        presets = {
            "Off": {
                "enabled": (),
                "values": (0.35, 0.25, 0.25, 0.04, 0.25, 0.25, 0.18),
            },
            "Subtle": {
                "enabled": ("scratches", "dust", "grain", "flicker"),
                "values": (0.18, 0.12, 0.14, 0.02, 0.15, 0.12, 0.08),
            },
            "Medium": {
                "enabled": ("scratches", "dust", "grain", "flicker", "vignette", "color_fade"),
                "values": (0.35, 0.25, 0.25, 0.04, 0.25, 0.25, 0.14),
            },
            "Heavy": {
                "enabled": (
                    "scratches",
                    "dust",
                    "grain",
                    "flicker",
                    "vignette",
                    "color_fade",
                    "scan_lines",
                ),
                "values": (0.70, 0.55, 0.45, 0.08, 0.42, 0.38, 0.24),
            },
        }
        preset = presets.get(self.video_effect_retro_preset.currentText())
        if preset is None:
            return
        enabled = set(preset["enabled"])
        scratch, dust, grain, flicker, vignette, color_fade, scan_lines = preset["values"]
        checkbox_values = (
            (self.video_effect_retro_scratches_enabled, "scratches"),
            (self.video_effect_retro_dust_enabled, "dust"),
            (self.video_effect_retro_grain_enabled, "grain"),
            (self.video_effect_retro_flicker_enabled, "flicker"),
            (self.video_effect_retro_vignette_enabled, "vignette"),
            (self.video_effect_retro_color_fade_enabled, "color_fade"),
            (self.video_effect_retro_scan_lines_enabled, "scan_lines"),
        )
        for checkbox, key in checkbox_values:
            previous = checkbox.blockSignals(True)
            checkbox.setChecked(key in enabled)
            checkbox.blockSignals(previous)
            for index in range(checkbox.parentWidget().layout().count()):
                widget = checkbox.parentWidget().layout().itemAt(index).widget()
                if widget is not None and widget is not checkbox:
                    widget.setVisible(checkbox.isChecked())
        for widget, value in (
            (self.video_effect_retro_scratch, scratch),
            (self.video_effect_retro_dust, dust),
            (self.video_effect_retro_grain, grain),
            (self.video_effect_retro_flicker, flicker),
            (self.video_effect_retro_vignette, vignette),
            (self.video_effect_retro_color_fade, color_fade),
            (self.video_effect_retro_scan_lines, scan_lines),
        ):
            previous = widget.blockSignals(True)
            widget.setValue(value)
            widget.blockSignals(previous)

    def mark_video_effect_retro_custom(self) -> None:
        if self.video_effect_retro_preset.currentText() == "Custom":
            return
        previous = self.video_effect_retro_preset.blockSignals(True)
        self.video_effect_retro_preset.setCurrentText("Custom")
        self.video_effect_retro_preset.blockSignals(previous)

    def make_group_collapsible(self, group: QGroupBox) -> None:
        group.setCheckable(True)
        group.setChecked(True)

        def set_expanded(expanded: bool) -> None:
            layout = group.layout()
            if layout is not None:
                for index in range(layout.count()):
                    item = layout.itemAt(index)
                    widget = item.widget()
                    if widget is not None:
                        widget.setVisible(expanded)
                    child_layout = item.layout()
                    if child_layout is not None:
                        for child_index in range(child_layout.count()):
                            child = child_layout.itemAt(child_index).widget()
                            if child is not None:
                                child.setVisible(expanded)
            group.setMaximumHeight(16777215 if expanded else 30)

        group.toggled.connect(set_expanded)

    def add_video_effect_batch_row(
        self, images: str = "", audios: str = "", output: str = "", primary: bool = False
    ) -> dict:
        row_widget = QWidget()
        row_layout = QVBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 6)
        row_layout.setSpacing(4)

        images_edit = self.video_effect_images_dir if primary else QLineEdit(images)
        audios_edit = self.video_effect_audios_dir if primary else QLineEdit(audios)
        output_edit = self.video_effect_output_dir if primary else QLineEdit(output)
        images_edit.setStyleSheet(
            "QLineEdit { background: #10262c; border: 1px solid #21b6cf; color: #d9faff; }"
            "QLineEdit:focus { border: 2px solid #39d8ff; }"
        )
        output_edit.setStyleSheet(
            "QLineEdit { background: #2a2112; border: 1px solid #d69a32; color: #ffe8b5; }"
            "QLineEdit:focus { border: 2px solid #f0b44c; }"
        )

        def folder_line(label: str, edit: QLineEdit, title: str) -> QWidget:
            wrapper = QWidget()
            layout = QHBoxLayout(wrapper)
            layout.setContentsMargins(0, 0, 0, 0)
            label_widget = QLabel(label)
            label_widget.setFixedWidth(52)
            layout.addWidget(label_widget)
            layout.addWidget(edit, 1)
            layout.addWidget(
                self.button("Browse", lambda: self.pick_video_effect_folder_for(edit, title))
            )
            return wrapper

        row_layout.addWidget(folder_line("Images", images_edit, "Images folder"))
        row_layout.addWidget(folder_line("Audios", audios_edit, "Audios folder"))
        output_line = folder_line("Output", output_edit, "Video Effect output folder")
        if not primary:
            output_line.layout().addWidget(
                self.button("X", lambda: self.remove_video_effect_batch_row(row))
            )
        row_layout.addWidget(output_line)

        row = {
            "widget": row_widget,
            "images": images_edit,
            "audios": audios_edit,
            "output": output_edit,
            "primary": primary,
        }
        self.video_effect_batch_rows.append(row)
        self.video_effect_batch_layout.addWidget(row_widget)
        images_edit.editingFinished.connect(lambda: self.report_video_effect_batch_row(row))
        audios_edit.editingFinished.connect(lambda: self.report_video_effect_batch_row(row))
        self.update_video_effect_batch_height()
        return row

    def add_video_effect_batch_row_clicked(self) -> None:
        self.add_video_effect_batch_row()

    def remove_video_effect_batch_row(self, row: dict) -> None:
        if row.get("primary") or row not in self.video_effect_batch_rows:
            return
        self.video_effect_batch_rows.remove(row)
        self.video_effect_batch_layout.removeWidget(row["widget"])
        row["widget"].deleteLater()
        self.update_video_effect_batch_height()

    def update_video_effect_batch_height(self) -> None:
        visible_rows = min(3, max(1, len(self.video_effect_batch_rows)))
        self.video_effect_batch_scroll.setFixedHeight(visible_rows * 104 + 4)

    def pick_video_effect_folder_for(self, edit: QLineEdit, title: str) -> None:
        path = QFileDialog.getExistingDirectory(self, title)
        if path:
            edit.setText(path)
            row = next(
                (item for item in self.video_effect_batch_rows if edit in (item["images"], item["audios"])),
                None,
            )
            if row:
                self.report_video_effect_batch_row(row)

    def report_video_effect_batch_row(self, row: dict) -> tuple[int | None, int | None]:
        images = self.count_video_effect_media(
            row["images"].text(), {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
        )
        audios = self.count_video_effect_media(
            row["audios"].text(), {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}
        )
        index = self.video_effect_batch_rows.index(row) + 1
        if images is not None or audios is not None:
            state = "OK" if images == audios and images is not None else "WARNING: counts differ"
            self.video_effect_log_message(
                f"[Batch {index}] images: {images or 0} | audios: {audios or 0} | {state}"
            )
        return images, audios

    def pick_video_effect_images_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Images folder")
        if path:
            self.video_effect_images_dir.setText(path)
            self.report_video_effect_media_counts()

    def pick_video_effect_audios_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Audios folder")
        if path:
            self.video_effect_audios_dir.setText(path)
            self.report_video_effect_media_counts()

    def pick_video_effect_output_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Video Effect output folder")
        if path:
            self.video_effect_output_dir.setText(path)

    def video_effect_log_message(self, message: str) -> None:
        log_event("UI | " + message)
        self.video_effect_log.appendPlainText(message)
        scrollbar = self.video_effect_log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def count_video_effect_media(self, folder_text: str, extensions: set[str]) -> int | None:
        folder_text = folder_text.strip()
        if not folder_text:
            return None
        folder = Path(folder_text)
        if not folder.is_dir():
            return None
        return sum(1 for path in folder.iterdir() if path.is_file() and path.suffix.lower() in extensions)

    def extract_leading_number(self, name: str) -> int | None:
        match = re.match(r"^\s*(\d+)", name)
        return int(match.group(1)) if match else None

    def extract_media_sequence_number(self, name: str, media_type: str) -> int | None:
        stem = Path(name).stem
        patterns = []
        if media_type == "video":
            patterns.append(r"^\s*segment[\s_-]*(\d+)")
        else:
            patterns.extend(
                [
                    r"^\s*(\d+)",
                    r"(?:image|img|scene|frame|photo|pic)[\s_-]*(\d+)",
                ]
            )
            patterns.append(r"(\d+)")
        for pattern in patterns:
            match = re.search(pattern, stem, flags=re.IGNORECASE)
            if match:
                return int(match.group(1))
        return None

    def list_media_files(
        self, folder: Path, extensions: set[str], recursive: bool = False
    ) -> list[Path]:
        if not recursive:
            return sorted(
                (
                    path
                    for path in folder.iterdir()
                    if path.is_file() and path.suffix.lower() in extensions
                ),
                key=lambda path: path.name.lower(),
            )
        media_files: list[Path] = []
        for root, _directories, filenames in os.walk(folder):
            root_path = Path(root)
            for filename in filenames:
                path = root_path / filename
                if path.suffix.lower() in extensions:
                    media_files.append(path)
        return sorted(media_files, key=lambda path: str(path).lower())

    def find_missing_media_numbers(
        self,
        folder_text: str,
        extensions: set[str],
        media_type: str = "image",
        recursive: bool = False,
    ) -> dict | None:
        folder_text = folder_text.strip()
        if not folder_text:
            return None
        folder = Path(folder_text)
        if not folder.is_dir():
            return None
        paths = self.list_media_files(folder, extensions, recursive)
        image_files = [
            path.name
            for path in paths
        ]
        ignored: list[str] = []
        number_to_files: dict[int, list[str]] = {}
        for name in image_files:
            number = self.extract_media_sequence_number(name, media_type)
            if number is None:
                ignored.append(name)
                continue
            number_to_files.setdefault(number, []).append(name)
        if not number_to_files:
            return {
                "total_files": len(image_files),
                "numbered_files": 0,
                "ignored_files": sorted(ignored),
                "min_number": None,
                "max_number": None,
                "missing_numbers": [],
                "duplicate_numbers": {},
            }
        numbers = sorted(number_to_files)
        missing_numbers = sorted(set(range(numbers[0], numbers[-1] + 1)) - set(numbers))
        duplicate_numbers = {
            number: sorted(files)
            for number, files in sorted(number_to_files.items())
            if len(files) > 1
        }
        return {
            "total_files": len(image_files),
            "numbered_files": sum(len(files) for files in number_to_files.values()),
            "ignored_files": sorted(ignored),
            "min_number": numbers[0],
            "max_number": numbers[-1],
            "missing_numbers": missing_numbers,
            "duplicate_numbers": duplicate_numbers,
        }

    def find_missing_image_numbers(self, folder_text: str) -> dict | None:
        return self.find_missing_media_numbers(folder_text, VIDEO_IMAGE_EXTS)

    def report_video_effect_missing_images(
        self, folder_text: str | None = None, batch_index: int | None = None
    ) -> None:
        folder_text = self.video_effect_images_dir.text() if folder_text is None else folder_text
        prefix = f"[Batch {batch_index}] " if batch_index is not None else ""
        if not folder_text.strip():
            self.video_effect_log_message(f"{prefix}Image sequence check | Images folder is empty.")
            return
        result = self.find_missing_image_numbers(folder_text)
        if result is None:
            self.video_effect_log_message(
                f"{prefix}Image sequence check | Folder does not exist: {folder_text.strip()}"
            )
            return
        if result["min_number"] is None:
            self.video_effect_log_message(
                f"{prefix}Image sequence check | {result['total_files']} image file(s), "
                "no leading numbers found."
            )
            return
        self.video_effect_log_message(
            f"{prefix}Image sequence check | "
            f"{result['numbered_files']}/{result['total_files']} numbered image file(s), "
            f"range {result['min_number']} -> {result['max_number']}."
        )
        if result["missing_numbers"]:
            missing_text = ", ".join(str(number) for number in result["missing_numbers"])
            self.video_effect_log_message(
                f"{prefix}Missing image numbers: {len(result['missing_numbers'])} | {missing_text}"
            )
        else:
            self.video_effect_log_message(f"{prefix}Missing image numbers: none.")
        if result["duplicate_numbers"]:
            duplicate_text = "; ".join(
                f"{number}: {len(files)} files" for number, files in result["duplicate_numbers"].items()
            )
            self.video_effect_log_message(f"{prefix}Duplicate image numbers: {duplicate_text}")
        if result["ignored_files"]:
            self.video_effect_log_message(
                f"{prefix}Ignored image files without a sequence number: "
                f"{len(result['ignored_files'])}"
            )

    def check_video_effect_image_folders(self) -> None:
        self.video_effect_log_message(
            f"Checking image folders for {len(self.video_effect_batch_rows)} batch(es)..."
        )
        for index, row in enumerate(self.video_effect_batch_rows, start=1):
            self.report_video_effect_missing_images(row["images"].text(), index)

    def check_video_effect_video_folders(self) -> None:
        if self.video_integrity_thread and self.video_integrity_thread.isRunning():
            self.video_effect_log_message("Video integrity check is already running.")
            return
        self.video_effect_log_message(
            f"Checking video folders for {len(self.video_effect_batch_rows)} batch(es)..."
        )
        for index, row in enumerate(self.video_effect_batch_rows, start=1):
            folder_text = row["output"].text().strip()
            prefix = f"[Batch {index}] "
            if not folder_text:
                self.video_effect_log_message(
                    f"{prefix}Video sequence check | Output folder is empty."
                )
                continue
            result = self.find_missing_media_numbers(
                folder_text, VIDEO_FILE_EXTS, media_type="video", recursive=False
            )
            if result is None:
                self.video_effect_log_message(
                    f"{prefix}Video sequence check | Folder does not exist: {folder_text}"
                )
                continue
            if result["min_number"] is None:
                self.video_effect_log_message(
                    f"{prefix}Video sequence check | {result['total_files']} video file(s), "
                    "no leading numbers found."
                )
                continue
            self.video_effect_log_message(
                f"{prefix}Video sequence check | "
                f"{result['numbered_files']}/{result['total_files']} numbered video file(s), "
                f"range {result['min_number']} -> {result['max_number']}."
            )
            if result["missing_numbers"]:
                missing_text = ", ".join(str(number) for number in result["missing_numbers"])
                self.video_effect_log_message(
                    f"{prefix}Missing video numbers: {len(result['missing_numbers'])} | "
                    f"{missing_text}"
                )
            else:
                self.video_effect_log_message(f"{prefix}Missing video numbers: none.")
            if result["duplicate_numbers"]:
                duplicate_text = "; ".join(
                    f"{number}: {len(files)} files"
                    for number, files in result["duplicate_numbers"].items()
                )
                self.video_effect_log_message(
                    f"{prefix}Duplicate video numbers: {duplicate_text}"
                )
            if result["ignored_files"]:
                self.video_effect_log_message(
                    f"{prefix}Ignored video files without a sequence number: "
                    f"{len(result['ignored_files'])}"
                )
        self.start_video_output_integrity_check()

    def start_video_output_integrity_check(self) -> None:
        videos: list[tuple[int, Path]] = []
        for batch_index, row in enumerate(self.video_effect_batch_rows, start=1):
            folder = Path(row["output"].text().strip())
            if not folder.is_dir():
                continue
            batch_videos = self.list_media_files(folder, VIDEO_FILE_EXTS, recursive=False)
            videos.extend((batch_index, path) for path in batch_videos)
        if not videos:
            self.video_effect_log_message(
                "Video integrity check | No video files found in the batch Output folders."
            )
            return

        self.video_effect_log_message(
            f"Video integrity check started | decoding {len(videos)} video file(s)..."
        )
        self.video_effect_check_videos_button.setEnabled(False)
        self.video_integrity_thread = QThread()
        self.video_integrity_worker = VideoIntegrityCheckWorker(videos)
        self.video_integrity_worker.moveToThread(self.video_integrity_thread)
        self.video_integrity_thread.started.connect(self.video_integrity_worker.run)
        self.video_integrity_worker.progress.connect(self.video_effect_log_message)
        self.video_integrity_worker.completed.connect(self.on_video_integrity_check_completed)
        self.video_integrity_worker.completed.connect(self.video_integrity_thread.quit)
        self.video_integrity_thread.finished.connect(self.on_video_integrity_thread_finished)
        self.video_integrity_thread.start()

    def on_video_integrity_check_completed(self, total: int, failed: int) -> None:
        if failed:
            self.video_effect_log_message(
                f"Video integrity check FAILED | {failed}/{total} corrupt video file(s). "
                "See CORRUPT VIDEO entries above."
            )
        else:
            self.video_effect_log_message(
                f"Video integrity check OK | {total}/{total} video file(s) decoded successfully."
            )

    def on_video_integrity_thread_finished(self) -> None:
        if self.video_integrity_worker is not None:
            self.video_integrity_worker.deleteLater()
        if self.video_integrity_thread is not None:
            self.video_integrity_thread.deleteLater()
        self.video_integrity_worker = None
        self.video_integrity_thread = None
        self.video_effect_check_videos_button.setEnabled(True)

    def merge_video_effect_output_folders(self) -> None:
        if self.video_output_merge_thread and self.video_output_merge_thread.isRunning():
            self.video_effect_log_message("Video output merge is already running.")
            return
        if self.video_integrity_thread and self.video_integrity_thread.isRunning():
            self.video_effect_log_message(
                "Wait for Check Video Output to finish before merging."
            )
            return
        if self.thread and self.thread.isRunning():
            self.video_effect_log_message(
                "Wait for the current render task to finish before merging Output videos."
            )
            return

        def natural_name_key(path: Path) -> list[object]:
            return [
                int(part) if part.isdigit() else part.lower()
                for part in re.split(r"(\d+)", path.name)
            ]

        jobs: list[tuple[int, Path, list[Path]]] = []
        for batch_index, row in enumerate(self.video_effect_batch_rows, start=1):
            output_root = Path(row["output"].text().strip())
            if not output_root.is_dir():
                self.video_effect_log_message(
                    f"[Batch {batch_index}] Merge skipped | Output folder does not exist."
                )
                continue
            videos = self.list_media_files(output_root, VIDEO_FILE_EXTS, recursive=False)
            videos.sort(key=natural_name_key)
            if not videos:
                self.video_effect_log_message(
                    f"[Batch {batch_index}] Merge skipped | No video files in Output root."
                )
                continue
            jobs.append((batch_index, output_root, videos))
            self.video_effect_log_message(
                f"[Batch {batch_index}] Merge queue | {len(videos)} root video file(s), "
                f"first: {videos[0].name}, last: {videos[-1].name}."
            )
        if not jobs:
            self.video_effect_log_message("Merge Video Output | Nothing to merge.")
            return

        self.video_effect_merge_output_button.setEnabled(False)
        self.video_effect_check_videos_button.setEnabled(False)
        self.video_output_merge_thread = QThread()
        self.video_output_merge_worker = OutputVideoMergeWorker(jobs)
        self.video_output_merge_worker.moveToThread(self.video_output_merge_thread)
        self.video_output_merge_thread.started.connect(self.video_output_merge_worker.run)
        self.video_output_merge_worker.progress.connect(self.video_effect_log_message)
        self.video_output_merge_worker.completed.connect(self.on_video_output_merge_completed)
        self.video_output_merge_worker.failed.connect(self.on_video_output_merge_failed)
        self.video_output_merge_worker.completed.connect(self.video_output_merge_thread.quit)
        self.video_output_merge_worker.failed.connect(self.video_output_merge_thread.quit)
        self.video_output_merge_thread.finished.connect(self.on_video_output_merge_thread_finished)
        self.video_effect_log_message(
            f"Merge Video Output started for {len(jobs)} batch(es)..."
        )
        self.video_output_merge_thread.start()

    def on_video_output_merge_completed(self, outputs: list[str]) -> None:
        self.video_effect_log_message(
            f"Merge Video Output completed | {len(outputs)} merged file(s)."
        )
        for output in outputs:
            self.video_effect_log_message(f"Merged output: {output}")

    def on_video_output_merge_failed(self, details: str) -> None:
        self.video_effect_log_message(f"Merge Video Output FAILED:\n{details[-3000:]}")

    def on_video_output_merge_thread_finished(self) -> None:
        if self.video_output_merge_worker is not None:
            self.video_output_merge_worker.deleteLater()
        if self.video_output_merge_thread is not None:
            self.video_output_merge_thread.deleteLater()
        self.video_output_merge_worker = None
        self.video_output_merge_thread = None
        self.video_effect_merge_output_button.setEnabled(True)
        self.video_effect_check_videos_button.setEnabled(True)

    def report_video_effect_media_counts(self) -> tuple[int | None, int | None]:
        image_count = self.count_video_effect_media(self.video_effect_images_dir.text(), VIDEO_IMAGE_EXTS)
        audio_count = self.count_video_effect_media(self.video_effect_audios_dir.text(), VIDEO_AUDIO_EXTS)
        if image_count is None and audio_count is None:
            return image_count, audio_count
        image_text = "not selected" if image_count is None else str(image_count)
        audio_text = "not selected" if audio_count is None else str(audio_count)
        if image_count is not None and audio_count is not None:
            usable = min(image_count, audio_count)
            if image_count == audio_count:
                status = f"OK: {usable} matched pair(s)."
            else:
                status = f"WARNING: counts differ; render will use {usable} pair(s)."
        else:
            status = "Choose both folders to compare counts."
        self.video_effect_log_message(
            f"Media count | images: {image_text} | audios: {audio_text} | {status}"
        )
        self.report_video_effect_missing_images()
        self.video_effect_status.setText(status)
        return image_count, audio_count

    def current_video_effect_session_dir(self, create: bool = False) -> Path | None:
        root_text = self.video_effect_output_dir.text().strip()
        if not root_text:
            return None
        root = Path(root_text) / "effect"
        if self.active_video_effect_output_dir and self.active_video_effect_output_dir.parent == root:
            return self.active_video_effect_output_dir
        if create:
            root.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.active_video_effect_output_dir = root / f"video_effect_{timestamp}"
            suffix = 2
            while self.active_video_effect_output_dir.exists():
                self.active_video_effect_output_dir = root / f"video_effect_{timestamp}_{suffix:02d}"
                suffix += 1
            self.active_video_effect_output_dir.mkdir(parents=True, exist_ok=True)
            return self.active_video_effect_output_dir
        return None

    def open_video_effect_output_folder(self) -> None:
        selected_root = Path(self.video_effect_output_dir.text())
        effect_root = selected_root / "effect"
        path = effect_root if effect_root.is_dir() else selected_root
        if path.is_dir():
            os.startfile(path)
        else:
            QMessageBox.warning(self, "Video Effect output folder", "The output folder does not exist yet.")

    def start_video_effect(self) -> None:
        try:
            if self.thread and self.thread.isRunning():
                raise RuntimeError("Another task is already running.")
            if self.video_effect_preflight_thread and self.video_effect_preflight_thread.isRunning():
                raise RuntimeError("Video Effect media preflight is already running.")
            self.active_task_ui = "video_effect"
            self.persist_settings("video_effect")
            self.video_effect_log.clear()
            if not VIDEO_EFFECT_SCRIPT.is_file():
                raise ValueError(
                    f"The bundled Video Effect pipeline is missing:\n{VIDEO_EFFECT_SCRIPT}"
                )
            jobs = []
            for index, row in enumerate(self.video_effect_batch_rows, 1):
                values = {
                    "images": row["images"].text().strip(),
                    "audios": row["audios"].text().strip(),
                    "output": row["output"].text().strip(),
                }
                if not any(values.values()):
                    continue
                if not Path(values["images"]).is_dir():
                    raise ValueError(f"Batch {index}: choose a valid images folder.")
                if not Path(values["audios"]).is_dir():
                    raise ValueError(f"Batch {index}: choose a valid audios folder.")
                if not values["output"]:
                    raise ValueError(f"Batch {index}: choose an output folder.")
                image_count, audio_count = self.report_video_effect_batch_row(row)
                if not image_count:
                    raise ValueError(f"Batch {index}: no supported image files were found.")
                if not audio_count:
                    raise ValueError(f"Batch {index}: no supported audio files were found.")
                if image_count != audio_count:
                    raise ValueError(
                        f"Batch {index}: image/audio counts differ "
                        f"({image_count} images, {audio_count} audios). Render stopped."
                    )
                values["image_count"] = image_count
                values["audio_count"] = audio_count
                jobs.append(values)
            if not jobs:
                raise ValueError("Add at least one complete Images / Audios / Output task.")

            self.start_video_effect_media_preflight(jobs)
        except Exception as exc:
            self.video_effect_log_message(f"Video Effect preflight stopped | {exc}")
            QMessageBox.critical(self, "Cannot render Video Effect", str(exc))

    def start_video_effect_media_preflight(self, jobs: list[dict]) -> None:
        self.video_effect_pending_jobs = jobs
        self.video_effect_render_button.setEnabled(False)
        self.video_effect_status.setText("Checking image and audio files before render...")
        self.video_effect_log_message(
            f"Preflight checking files | {len(jobs)} batch(es). Render is waiting..."
        )
        self.video_effect_preflight_thread = QThread()
        self.video_effect_preflight_worker = VideoEffectMediaPreflightWorker(jobs)
        self.video_effect_preflight_worker.moveToThread(self.video_effect_preflight_thread)
        self.video_effect_preflight_thread.started.connect(
            self.video_effect_preflight_worker.run
        )
        self.video_effect_preflight_worker.progress.connect(self.video_effect_log_message)
        self.video_effect_preflight_worker.completed.connect(
            self.on_video_effect_media_preflight_completed
        )
        self.video_effect_preflight_worker.completed.connect(
            self.video_effect_preflight_thread.quit
        )
        self.video_effect_preflight_thread.finished.connect(
            self.on_video_effect_media_preflight_thread_finished
        )
        self.video_effect_preflight_thread.start()

    def on_video_effect_media_preflight_completed(self, errors: list[str]) -> None:
        if errors:
            self.video_effect_log_message(
                f"Preflight FAILED | {len(errors)} corrupt/problem file(s). Render stopped."
            )
            for error in errors:
                self.video_effect_log_message(error)
            self.video_effect_status.setText(
                f"Render stopped: {len(errors)} corrupt/problem file(s)."
            )
            self.video_effect_pending_jobs = []
            QMessageBox.critical(
                self,
                "Video Effect media check failed",
                f"Found {len(errors)} corrupt/problem image or audio file(s).\n"
                "Render was stopped. See the processing log for full paths.",
            )
            return

        self.video_effect_log_message(
            "Preflight OK | all image and audio files are readable. Starting render..."
        )
        jobs = self.video_effect_pending_jobs
        self.video_effect_pending_jobs = []
        self.video_effect_batch_queue = jobs
        self.video_effect_batch_outputs = []
        self.video_effect_batch_index = 0
        self.video_effect_batch_started_at = time.monotonic()
        self.video_effect_batch_stopping = False
        self.update_video_effect_dimensions()
        self._start_next_video_effect_job()

    def on_video_effect_media_preflight_thread_finished(self) -> None:
        if self.video_effect_preflight_worker is not None:
            self.video_effect_preflight_worker.deleteLater()
        if self.video_effect_preflight_thread is not None:
            self.video_effect_preflight_thread.deleteLater()
        self.video_effect_preflight_worker = None
        self.video_effect_preflight_thread = None
        if not (self.thread and self.thread.isRunning()):
            self.video_effect_render_button.setEnabled(True)

    def _start_next_video_effect_job(self) -> None:
        job = self.video_effect_batch_queue[self.video_effect_batch_index]
        root = Path(job["output"]) / "effect"
        root.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = root / f"video_effect_{timestamp}_batch_{self.video_effect_batch_index + 1:02d}"
        suffix = 2
        while output_dir.exists():
            output_dir = root / (
                f"video_effect_{timestamp}_batch_{self.video_effect_batch_index + 1:02d}_{suffix:02d}"
            )
            suffix += 1
        output_dir.mkdir(parents=True)
        self.active_video_effect_output_dir = output_dir
        self.video_effect_job_succeeded = False
        self.video_effect_log_message(
            f"=== Batch {self.video_effect_batch_index + 1}/{len(self.video_effect_batch_queue)} ==="
        )
        self.video_effect_log_message(
            f"Batch segments: {min(job['image_count'], job['audio_count'])} | requested workers: "
            f"{self.video_effect_workers.value()} | codec: {self.video_effect_codec.currentText()}"
        )
        self.worker = VideoEffectWorker(
                VIDEO_EFFECT_SCRIPT,
                Path(job["images"]),
                Path(job["audios"]),
                output_dir,
                self.video_effect_width.value(),
                self.video_effect_height.value(),
                self.video_effect_fps.value(),
                self.video_effect_crf.value(),
                self.video_effect_codec.currentText(),
                self.video_effect_workers.value(),
                self.video_effect_pattern.text().strip() or "pan_lr,pan_ud,zoom_in,zoom_out,combo",
                self.video_effect_random_effects.isChecked(),
                self.video_effect_bounce.isChecked(),
                self.video_effect_zoom_scale.value(),
                self.video_effect_base_crop.value(),
                self.video_effect_edge_reach.value(),
                self.video_effect_face_safe.value(),
                self.video_effect_speed.value(),
                self.video_effect_pre_silence.value(),
                self.video_effect_min_motion.value(),
                self.video_effect_combo_radius.value(),
                self.video_effect_combo_offset_x.value(),
                self.video_effect_combo_offset_y.value(),
                self.video_effect_retro_preset.currentText(),
                self.video_effect_retro_scratches_enabled.isChecked(),
                self.video_effect_retro_scratch.value(),
                self.video_effect_retro_dust_enabled.isChecked(),
                self.video_effect_retro_dust.value(),
                self.video_effect_retro_grain_enabled.isChecked(),
                self.video_effect_retro_grain.value(),
                self.video_effect_retro_flicker_enabled.isChecked(),
                self.video_effect_retro_flicker.value(),
                self.video_effect_retro_vignette_enabled.isChecked(),
                self.video_effect_retro_vignette.value(),
                self.video_effect_retro_color_fade_enabled.isChecked(),
                self.video_effect_retro_color_fade.value(),
                self.video_effect_retro_scan_lines_enabled.isChecked(),
                self.video_effect_retro_scan_lines.value(),
                self.video_effect_merge.isChecked(),
                True,
            )
        self.thread = QThread()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.on_video_effect_progress)
        self.worker.segment_progress.connect(self.on_video_effect_segment_progress)
        self.worker.completed.connect(self.on_video_effect_completed)
        self.worker.cancelled.connect(self.on_video_effect_cancelled)
        self.worker.failed.connect(self.on_video_effect_failed)
        self.worker.completed.connect(self.thread.quit)
        self.worker.cancelled.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.finished.connect(self.on_video_effect_thread_finished)
        self.render_started_at = time.monotonic()
        self.set_busy(
            True,
            f"Starting batch {self.video_effect_batch_index + 1}/{len(self.video_effect_batch_queue)}...",
        )
        self.video_effect_progress.setRange(0, min(job["image_count"], job["audio_count"]))
        self.video_effect_progress.setValue(0)
        self.thread.start()

    def merge_zonos2_audio(self) -> None:
        try:
            if self.thread and self.thread.isRunning():
                raise RuntimeError("Another task is already running.")
            source_dir = self.current_zonos2_session_dir()
            if source_dir is None or not source_dir.is_dir():
                raise ValueError("No active ZONOS2 render session exists.")
            self.active_task_ui = "zonos2"
            self.worker = MergeWorker(
                source_dir, self.zonos2_output_format.currentText(), self.zonos2_merge_pause.value()
            )
            self.thread = QThread()
            self.worker.moveToThread(self.thread)
            self.thread.started.connect(self.worker.run)
            self.worker.progress.connect(self.on_merge_progress)
            self.worker.completed.connect(self.on_merge_completed)
            self.worker.failed.connect(self.on_merge_failed)
            self.worker.completed.connect(self.thread.quit)
            self.worker.failed.connect(self.thread.quit)
            self.thread.finished.connect(self.on_task_finished)
            self.set_busy(True, "Preparing ZONOS2 audio merge...")
            self.thread.start()
        except Exception as exc:
            QMessageBox.critical(self, "Cannot merge ZONOS2 audio", str(exc))

    def start_zonos2(
        self,
        segment_limit: int | None = None,
        start_override: int | None = None,
        end_override: int | None = None,
        overwrite_override: bool | None = None,
    ) -> None:
        try:
            if self.thread and self.thread.isRunning():
                raise RuntimeError("Another task is already running.")
            self.active_task_ui = "zonos2"
            self.persist_settings("voice_clone")
            input_path = Path(self.zonos2_input_file.text())
            if not input_path.is_file():
                raise ValueError("Choose a valid ZONOS2 SRT/TXT input file.")
            output_text = self.zonos2_output_dir.text().strip()
            if not output_text:
                raise ValueError("Choose a ZONOS2 output folder.")
            server_url = self.zonos2_server_url.text().strip()
            if not server_url.startswith(("http://", "https://")):
                raise ValueError("ZONOS2 server URL must start with http:// or https://.")
            self.zonos2_status.setText("Checking ZONOS2 server...")
            self.verify_zonos2_server(server_url)
            segments = parse_input(input_path)
            start_position = start_override or 1
            end_position = end_override or len(segments)
            if start_position > end_position:
                raise ValueError("Render range start must be less than or equal to end.")
            output_dir = self.current_zonos2_session_dir(create=True)
            if output_dir is None:
                raise ValueError("Choose a ZONOS2 output folder.")
            if segment_limit:
                output_dir = output_dir / "_preview"
            overwrite = bool(overwrite_override)
            if overwrite:
                width = max(3, len(str(len(segments))))
                existing = [
                    output_dir / f"{position:0{width}d}.{self.zonos2_output_format.currentText()}"
                    for position in range(start_position, end_position + 1)
                    if (
                        output_dir / f"{position:0{width}d}.{self.zonos2_output_format.currentText()}"
                    ).is_file()
                ]
                if existing:
                    answer = QMessageBox.question(
                        self,
                        "Overwrite existing ZONOS2 files?",
                        f"{len(existing)} existing file(s) in range {start_position}-{end_position} "
                        "will be overwritten.",
                    )
                    if answer != QMessageBox.StandardButton.Yes:
                        return
            selected_voice = str(
                self.zonos2_voice.currentData() or self.zonos2_voice.currentText()
            ).strip()
            reference_audio = ""
            voice_id = selected_voice
            if selected_voice.startswith("profile:"):
                profile = self.store.load(selected_voice.removeprefix("profile:"))
                reference_audio = profile["reference_audio"]
                voice_id = ""
            self.worker = Zonos2Worker(
                server_url,
                input_path,
                output_dir,
                self.zonos2_output_format.currentText(),
                str(self.zonos2_language.currentData()),
                self.zonos2_speed.value(),
                self.zonos2_seed.value(),
                self.zonos2_accurate_mode.isChecked(),
                voice_id,
                self.zonos2_temperature.value(),
                self.zonos2_topk.value(),
                self.zonos2_min_p.value(),
                self.zonos2_repetition_penalty.value(),
                self.zonos2_clean_speaker_background.isChecked(),
                segment_limit,
                self.zonos2_cooldown_seconds.value(),
                start_position,
                end_position,
                overwrite,
                self.zonos2_normalize_audio.isChecked(),
                reference_audio=reference_audio,
                session_id=self.zonos2_session_id,
            )
            self.thread = QThread()
            self.worker.moveToThread(self.thread)
            self.thread.started.connect(self.worker.run)
            self.worker.progress.connect(self.on_progress)
            self.worker.segment_status.connect(self.on_zonos2_segment_status)
            self.worker.completed.connect(self.on_completed)
            self.worker.cancelled.connect(self.on_cancelled)
            self.worker.failed.connect(self.on_failed)
            self.worker.completed.connect(self.thread.quit)
            self.worker.cancelled.connect(self.thread.quit)
            self.worker.failed.connect(self.thread.quit)
            self.thread.finished.connect(self.on_task_finished)
            self.render_started_at = time.monotonic()
            self.refresh_zonos2_segment_table()
            self.set_busy(True, "Connecting to ZONOS2 server...")
            self.append_log(f"Connecting to ZONOS2 server at {server_url}.")
            self.zonos2_progress.setRange(0, len(segments))
            self.zonos2_progress.setValue(0)
            self.thread.start()
        except Exception as exc:
            QMessageBox.critical(self, "Cannot render with ZONOS2", str(exc))

    def start_render(
        self,
        segment_limit: int | None = None,
        start_override: int | None = None,
        end_override: int | None = None,
        overwrite_override: bool | None = None,
        batch_queue: list[dict] | None = None,
    ) -> None:
        global _MOSS_RUNTIME_CACHE
        try:
            if self.thread and self.thread.isRunning():
                raise RuntimeError("Another task is already running.")
            if _MOSS_RUNTIME_CACHE:
                _MOSS_RUNTIME_CACHE.clear()
                gc.collect()
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except Exception:
                    pass
            self.active_task_ui = "omnivoice"
            self.persist_settings("voice_clone")
            
            if batch_queue:
                self.is_batch_running = True
                self.render_queue = list(batch_queue)
                self.process_next_batch_item(segment_limit, start_override, end_override, overwrite_override)
                return
            else:
                self.is_batch_running = False
                self.render_queue = []
                self.current_rendering_file_name = Path(self.get_active_input_path()).name if self.get_active_input_path() else ""

            profile_name = str(self.voice_profile.currentData() or "")
            if not profile_name:
                raise ValueError("Create or select a saved voice profile first.")
            input_path = Path(self.input_file.text())
            output_text = self.output_dir.text().strip()
            if not output_text:
                raise ValueError("Choose an output folder.")
            output_dir = self.current_session_dir(create=True)
            if output_dir is None:
                raise ValueError("Choose an output folder.")
            if segment_limit:
                output_dir = output_dir / "_preview"
            segments = parse_input(input_path)
            start_position = start_override or 1
            end_position = end_override or len(segments)
            if start_position > end_position:
                raise ValueError("Render range start must be less than or equal to end.")
            overwrite_requested = bool(overwrite_override)
            voice_change = self.resolve_omnivoice_voice_change(
                profile_name,
                output_dir,
                len(segments),
                start_position,
                end_position,
                overwrite_requested,
            )
            if voice_change is None:
                return
            output_suffix, overwrite = voice_change
            if overwrite_requested:
                existing = [
                    self.segment_audio_path(position)
                    for position in range(start_position, end_position + 1)
                    if self.segment_audio_path(position).is_file()
                ]
                if existing:
                    answer = QMessageBox.question(
                        self,
                        "Overwrite existing voice-over files?",
                        f"{len(existing)} existing file(s) in range {start_position}-{end_position} "
                        "will be overwritten.",
                    )
                    if answer != QMessageBox.StandardButton.Yes:
                        return

            self.worker = RenderWorker(
                self.store.load(profile_name),
                input_path,
                output_dir,
                self.model_name.text().strip() or DEFAULT_MODEL,
                self.steps.value(),
                self.fit_timeline.isChecked(),
                self.output_format.currentText(),
                segment_limit,
                self.compute_device.currentData(),
                self.cooldown_seconds.value(),
                self.reload_every.value(),
                start_position,
                end_position,
                overwrite,
                self.normalize_audio.isChecked(),
                self.language.currentData(),
                self.speaking_style.currentText().strip() if self.use_speaking_style.isChecked() else "",
                self.use_speaking_style.isChecked() and self.style_mode.currentData() == "auto",
                dict(self.segment_style_overrides) if self.use_speaking_style.isChecked() else {},
                output_suffix=output_suffix,
            )
            self.thread = QThread()
            self.worker.moveToThread(self.thread)
            self.thread.started.connect(self.worker.run)
            self.worker.progress.connect(self.on_progress)
            self.worker.segment_status.connect(self.on_segment_status)
            self.worker.completed.connect(self.on_completed)
            self.worker.cancelled.connect(self.on_cancelled)
            self.worker.failed.connect(self.on_failed)
            self.worker.completed.connect(self.thread.quit)
            self.worker.cancelled.connect(self.thread.quit)
            self.worker.failed.connect(self.thread.quit)
            self.thread.finished.connect(self.on_task_finished)
            total = min(len(segments), segment_limit) if segment_limit else len(segments)
            self.status.setText("Loading model for preview..." if segment_limit else "Loading model...")
            self.append_log(
                f"Loading OmniVoice checkpoint '{self.model_name.text().strip() or DEFAULT_MODEL}'. "
                "Missing files will download automatically."
            )
            self.set_busy(True, self.status.text())
            self.render_started_at = time.monotonic()
            self.progress.setRange(0, total)
            self.progress.setValue(0)
            self.thread.start()
        except Exception as exc:
            QMessageBox.critical(self, "Cannot render", str(exc))

    def process_next_batch_item(
        self,
        segment_limit: int | None = None,
        start_override: int | None = None,
        end_override: int | None = None,
        overwrite_override: bool | None = None,
    ) -> None:
        if not self.render_queue:
            self.is_batch_running = False
            self.current_rendering_file_name = ""
            self.status.setText("Batch rendering completed successfully.")
            self.append_log("Batch rendering completed successfully.")
            self.set_busy(False)
            QMessageBox.information(self, "Batch Completed", "All tasks in the batch queue have finished!")
            return

        next_row = self.render_queue.pop(0)
        next_row["view_radio"].setChecked(True)
        self.current_view_row = next_row
        self.refresh_segment_table()

        input_path_str = next_row["input_edit"].text().strip()
        output_path_str = next_row["output_edit"].text().strip()
        input_path = Path(input_path_str)
        self.current_rendering_file_name = input_path.name

        self.append_log(f"Starting batch item: {self.current_rendering_file_name}")

        try:
            profile_name = str(self.voice_profile.currentData() or "")
            if not profile_name:
                raise ValueError("Create or select a saved voice profile first.")
            if not input_path.is_file():
                raise ValueError(f"SRT/TXT input file does not exist: {input_path_str}")
            if not output_path_str:
                raise ValueError("Output folder is empty.")

            self.active_output_dir = None
            output_dir = self.current_session_dir(create=True)
            if output_dir is None:
                raise ValueError("Choose an output folder.")

            segments = parse_input(input_path)
            start_position = start_override or 1
            end_position = end_override or len(segments)
            overwrite = bool(overwrite_override)
            output_suffix = ""

            self.worker = RenderWorker(
                self.store.load(profile_name),
                input_path,
                output_dir,
                self.model_name.text().strip() or DEFAULT_MODEL,
                self.steps.value(),
                self.fit_timeline.isChecked(),
                self.output_format.currentText(),
                segment_limit,
                self.compute_device.currentData(),
                self.cooldown_seconds.value(),
                self.reload_every.value(),
                start_position,
                end_position,
                overwrite,
                self.normalize_audio.isChecked(),
                self.language.currentData(),
                self.speaking_style.currentText().strip() if self.use_speaking_style.isChecked() else "",
                self.use_speaking_style.isChecked() and self.style_mode.currentData() == "auto",
                dict(self.segment_style_overrides) if self.use_speaking_style.isChecked() else {},
                output_suffix=output_suffix,
            )
            self.thread = QThread()
            self.worker.moveToThread(self.thread)
            self.thread.started.connect(self.worker.run)
            self.worker.progress.connect(self.on_progress)
            self.worker.segment_status.connect(self.on_segment_status)
            self.worker.completed.connect(self.on_completed)
            self.worker.cancelled.connect(self.on_cancelled)
            self.worker.failed.connect(self.on_failed)
            self.worker.completed.connect(self.thread.quit)
            self.worker.cancelled.connect(self.thread.quit)
            self.worker.failed.connect(self.thread.quit)
            self.thread.finished.connect(self.on_task_finished)

            total = len(segments)
            self.status.setText(f"Loading model for {self.current_rendering_file_name}...")
            self.set_busy(True, self.status.text())
            self.render_started_at = time.monotonic()
            self.progress.setRange(0, total)
            self.progress.setValue(0)
            self.thread.start()

        except Exception as exc:
            self.append_log(f"Error starting batch item {self.current_rendering_file_name}: {exc}")
            answer = QMessageBox.question(
                self,
                "Batch Rendering Error",
                f"Failed to start rendering for '{self.current_rendering_file_name}': {exc}\n\nDo you want to continue with the rest of the batch?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if answer == QMessageBox.StandardButton.Yes:
                self.process_next_batch_item(segment_limit, start_override, end_override, overwrite_override)
            else:
                self.is_batch_running = False
                self.set_busy(False)

    def merge_audio(self) -> None:
        try:
            if self.thread and self.thread.isRunning():
                raise RuntimeError("Another task is already running.")
            output_text = self.output_dir.text().strip()
            if not output_text:
                raise ValueError("Choose an output folder.")
            source_dir = self.current_session_dir()
            if source_dir is None or not source_dir.is_dir():
                raise ValueError(
                    "No active render session exists. Render audio in this app session before merging."
                )

            self.active_task_ui = "omnivoice"
            self.persist_settings("voice_clone")
            pause_seconds = self.merge_pause.value()
            self.append_log(f"Merging with {pause_seconds:.2f} second(s) between files.")
            self.worker = MergeWorker(
                source_dir,
                self.output_format.currentText(),
                pause_seconds,
                self.active_omnivoice_suffix,
            )
            self.thread = QThread()
            self.worker.moveToThread(self.thread)
            self.thread.started.connect(self.worker.run)
            self.worker.progress.connect(self.on_merge_progress)
            self.worker.completed.connect(self.on_merge_completed)
            self.worker.failed.connect(self.on_merge_failed)
            self.worker.completed.connect(self.thread.quit)
            self.worker.failed.connect(self.thread.quit)
            self.thread.finished.connect(self.on_task_finished)
            self.set_busy(True, "Preparing audio merge...")
            self.thread.start()
        except Exception as exc:
            QMessageBox.critical(self, "Cannot merge audio", str(exc))

    def retry_batch_normalization(self) -> None:
        try:
            if self.thread and self.thread.isRunning():
                raise RuntimeError("Another task is already running.")
            source_dir = self.current_session_dir()
            if source_dir is None or not source_dir.is_dir():
                selected = QFileDialog.getExistingDirectory(
                    self,
                    "Select completed voice-over session",
                    self.output_dir.text().strip(),
                )
                if not selected:
                    return
                source_dir = Path(selected)
                self.active_output_dir = source_dir
                self.active_omnivoice_suffix = ""

            self.active_task_ui = "omnivoice"
            self.append_log(f"Retrying completed-batch normalization in {source_dir}")
            self.worker = NormalizeBatchWorker(
                source_dir,
                self.output_format.currentText(),
                self.active_omnivoice_suffix,
            )
            self.thread = QThread()
            self.worker.moveToThread(self.thread)
            self.thread.started.connect(self.worker.run)
            self.worker.progress.connect(self.on_merge_progress)
            self.worker.completed.connect(self.on_batch_normalize_completed)
            self.worker.failed.connect(self.on_batch_normalize_failed)
            self.worker.completed.connect(self.thread.quit)
            self.worker.failed.connect(self.thread.quit)
            self.thread.finished.connect(self.on_task_finished)
            self.set_busy(True, "Retrying completed-batch normalization...")
            self.thread.start()
        except Exception as exc:
            QMessageBox.critical(self, "Cannot normalize batch", str(exc))

    def on_batch_normalize_completed(self, source: str) -> None:
        message = f"Batch normalization completed: {source}"
        self.status.setText(message)
        self.append_log(message)
        self.refresh_segment_table()
        QApplication.beep()
        QMessageBox.information(self, "Batch normalization completed", message)

    def on_batch_normalize_failed(self, details: str) -> None:
        message = (
            "Batch normalization could not finish. Close any audio player using the files, "
            "then click Retry batch normalization."
        )
        self.status.setText(message)
        self.append_log(details)
        QMessageBox.warning(
            self, "Batch normalization interrupted", f"{message}\n\n{details[-3000:]}"
        )

    def on_merge_progress(self, message: str) -> None:
        _, status_label = self.task_progress_widgets()
        status_label.setText(message)
        self.append_log(message)

    def on_merge_completed(self, destination: str) -> None:
        _, status_label = self.task_progress_widgets()
        status_label.setText(f"Merged audio saved: {destination}")
        self.append_log(status_label.text())
        QApplication.beep()
        os.startfile(Path(destination).parent)
        QMessageBox.information(self, "Merge completed", status_label.text())

    def on_merge_failed(self, details: str) -> None:
        _, status_label = self.task_progress_widgets()
        status_label.setText("Audio merge failed.")
        self.append_log(details)
        QMessageBox.critical(self, "Audio merge failed", details[-4000:])

    def on_video_effect_progress(self, message: str) -> None:
        self.video_effect_status.setText(message[:180])
        if message != "Rendering current segment...":
            self.append_log(message)

    def on_video_effect_segment_progress(self, current: int, total: int, filename: str) -> None:
        self.video_effect_progress.setRange(0, total)
        self.video_effect_progress.setValue(current)
        message = f"{current}/{total} completed: {filename}"
        self.video_effect_status.setText(message)

    def on_video_effect_completed(self, output_dir: str) -> None:
        elapsed = time.monotonic() - self.render_started_at if self.render_started_at else 0
        duration = time.strftime("%H:%M:%S", time.gmtime(elapsed))
        self.video_effect_progress.setRange(0, 100)
        self.video_effect_progress.setValue(100)
        message = (
            f"Batch {self.video_effect_batch_index + 1}/{len(self.video_effect_batch_queue)} "
            f"completed in {duration}: {output_dir}"
        )
        self.video_effect_status.setText(message)
        self.append_log(message)
        self.video_effect_batch_outputs.append(output_dir)
        self.video_effect_job_succeeded = True

    def on_video_effect_thread_finished(self) -> None:
        self.worker = None
        self.thread = None
        if (
            self.video_effect_job_succeeded
            and not self.video_effect_batch_stopping
            and self.video_effect_batch_index + 1 < len(self.video_effect_batch_queue)
        ):
            self.video_effect_batch_index += 1
            self._start_next_video_effect_job()
            return
        self.set_busy(False)
        self.video_effect_render_button.setEnabled(True)
        if self.video_effect_job_succeeded and not self.video_effect_batch_stopping:
            elapsed = (
                time.monotonic() - self.video_effect_batch_started_at
                if self.video_effect_batch_started_at
                else 0
            )
            duration = time.strftime("%H:%M:%S", time.gmtime(elapsed))
            total = len(self.video_effect_batch_outputs)
            message = f"Video Effect batch completed: {total} task(s) in {duration}."
            self.video_effect_status.setText(message)
            self.append_log(message)
            QApplication.beep()
            QMessageBox.information(
                self,
                "Video Effect batch completed",
                f"Completed {total} task(s).\n\nTotal render time: {duration}\n\n"
                + "\n".join(self.video_effect_batch_outputs),
            )
        self.video_effect_batch_queue = []

    def on_video_effect_cancelled(self, message: str) -> None:
        self.video_effect_progress.setRange(0, 100)
        self.video_effect_progress.setValue(0)
        self.video_effect_status.setText(message)
        self.append_log(message)
        self.video_effect_job_succeeded = False
        QMessageBox.information(self, "Video Effect stopped", message)

    def on_video_effect_failed(self, details: str) -> None:
        self.video_effect_progress.setRange(0, 100)
        self.video_effect_progress.setValue(0)
        self.video_effect_status.setText("Video Effect render failed.")
        self.append_log(details)
        self.video_effect_job_succeeded = False
        QMessageBox.critical(self, "Video Effect render failed", details[-4000:])

    def on_progress(self, current: int, total: int, text: str) -> None:
        progress, status_label = self.task_progress_widgets()
        progress.setMaximum(total)
        progress.setValue(current)
        if self.is_batch_running and self.current_rendering_file_name:
            status_text = f"[{self.current_rendering_file_name}] {current}/{total}: {text[:100]}"
        else:
            status_text = f"{current}/{total}: {text[:100]}"
        status_label.setText(status_text)
        self.append_log(status_text)

    def on_segment_status(self, position: int, status: str) -> None:
        if 1 <= position <= self.segment_table.rowCount():
            self.segment_table.setItem(position - 1, 3, QTableWidgetItem(status))
            actions = self.segment_table.cellWidget(position - 1, 5)
            if actions:
                buttons = actions.findChildren(QPushButton)
                if len(buttons) >= 3:
                    completed = status == "Completed"
                    buttons[0].setEnabled(completed)
                    buttons[2].setEnabled(completed)

    def on_zonos2_segment_status(self, position: int, status: str) -> None:
        if 1 <= position <= self.zonos2_segment_table.rowCount():
            self.zonos2_segment_table.setItem(position - 1, 3, QTableWidgetItem(status))
            actions = self.zonos2_segment_table.cellWidget(position - 1, 4)
            if actions:
                buttons = actions.findChildren(QPushButton)
                if len(buttons) >= 3:
                    completed = status == "Completed"
                    buttons[0].setEnabled(completed)
                    buttons[2].setEnabled(completed)

    def on_moss_segment_status(self, position: int, status: str) -> None:
        if 1 <= position <= self.moss_segment_table.rowCount():
            status_item = QTableWidgetItem(status)
            if status in {"Needs review", "Review required · Listen"}:
                status_item.setForeground(QColor("#ff6868"))
            elif status in {"Verified", "Auto-fixed · Listen"}:
                status_item.setForeground(QColor("#67d98b"))
            self.moss_segment_table.setItem(position - 1, 3, status_item)
            actions = self.moss_segment_table.cellWidget(position - 1, 4)
            if actions:
                buttons = actions.findChildren(QPushButton)
                if len(buttons) >= 3:
                    audio_available = status in {
                        "Completed", "Skipped", "Verified", "Needs review"
                    } or "Listen" in status
                    buttons[0].setEnabled(audio_available)
                    buttons[2].setEnabled(audio_available)

    def on_completed(self, output_dir: str) -> None:
        elapsed = time.monotonic() - self.render_started_at if self.render_started_at else 0
        duration = time.strftime("%H:%M:%S", time.gmtime(elapsed))
        _, status_label = self.task_progress_widgets()
        status_label.setText(f"Completed in {duration}: {output_dir}")
        self.append_log(status_label.text())
        self.refresh_segment_table()
        self.refresh_zonos2_segment_table()
        self.refresh_moss_segments()
        QApplication.beep()
        if self.is_batch_running:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(100, lambda: self.process_next_batch_item())
            return
        os.startfile(output_dir)
        QMessageBox.information(
            self, "Completed", f"Audio files saved to:\n{output_dir}\n\nTotal generation time: {duration}"
        )

    def on_cancelled(self, message: str) -> None:
        _, status_label = self.task_progress_widgets()
        status_label.setText(message)
        self.append_log(message)
        self.refresh_segment_table()
        self.refresh_zonos2_segment_table()
        self.refresh_moss_segments()
        if self.is_batch_running:
            self.is_batch_running = False
            self.current_rendering_file_name = ""
            QMessageBox.information(self, "Render stopped", "Batch rendering cancelled by user.")
            return
        QMessageBox.information(self, "Render stopped", message)

    def on_failed(self, details: str) -> None:
        _, status_label = self.task_progress_widgets()
        normalization_locked = "Retry batch normalization" in details
        status_label.setText(
            "Voice files rendered; batch normalization needs retry."
            if normalization_locked
            else "Render failed"
        )
        self.append_log(details)
        self.refresh_segment_table()
        self.refresh_zonos2_segment_table()
        self.refresh_moss_segments()
        if self.is_batch_running:
            answer = QMessageBox.question(
                self,
                "Batch Rendering Error",
                f"Rendering failed for '{self.current_rendering_file_name}': {details[-500:]}\n\nDo you want to continue with the next task in the batch?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if answer == QMessageBox.StandardButton.Yes:
                from PySide6.QtCore import QTimer
                QTimer.singleShot(100, lambda: self.process_next_batch_item())
            else:
                self.is_batch_running = False
                self.current_rendering_file_name = ""
                self.set_busy(False)
            return
        if normalization_locked:
            QMessageBox.warning(
                self,
                "Batch normalization interrupted",
                "Voice files were rendered successfully, but one file is open in another "
                "application. Close the audio player, then click Retry batch normalization."
                f"\n\n{details[-3000:]}",
            )
        else:
            QMessageBox.critical(self, "Render failed", details[-4000:])


def create_startup_splash() -> QSplashScreen:
    pixmap = QPixmap(520, 260)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    background = QLinearGradient(0, 0, 520, 260)
    background.setColorAt(0.0, QColor("#101827"))
    background.setColorAt(0.55, QColor("#162235"))
    background.setColorAt(1.0, QColor("#0b1018"))
    painter.setBrush(background)
    painter.setPen(QColor("#2c8fb7"))
    painter.drawRoundedRect(QRectF(1, 1, 518, 258), 24, 24)

    accent = QLinearGradient(28, 40, 210, 40)
    accent.setColorAt(0.0, QColor("#31d3ff"))
    accent.setColorAt(1.0, QColor("#7cf0c8"))
    painter.setBrush(accent)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(QRectF(30, 34, 86, 8), 4, 4)

    painter.setPen(QColor("#f3f8ff"))
    title_font = QFont("Segoe UI", 24, QFont.Weight.DemiBold)
    painter.setFont(title_font)
    painter.drawText(QRectF(30, 58, 460, 42), Qt.AlignmentFlag.AlignLeft, f"{APP_NAME} {APP_VERSION}")

    painter.setPen(QColor("#9fb3c9"))
    body_font = QFont("Segoe UI", 11)
    painter.setFont(body_font)
    painter.drawText(
        QRectF(32, 112, 450, 48),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
        "Preparing voice tools, profiles, and creative workspace...",
    )

    painter.setPen(QColor("#27384f"))
    painter.setBrush(QColor("#101826"))
    painter.drawRoundedRect(QRectF(32, 188, 456, 16), 8, 8)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(accent)
    painter.drawRoundedRect(QRectF(36, 192, 220, 8), 4, 4)

    painter.setPen(QColor("#6fd9ff"))
    small_font = QFont("Segoe UI", 9)
    painter.setFont(small_font)
    painter.drawText(QRectF(32, 220, 456, 24), Qt.AlignmentFlag.AlignLeft, "Launching app...")
    painter.end()

    splash = QSplashScreen(pixmap)
    splash.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
    return splash


class ActivationDialog(QDialog):
    def __init__(self, request_id: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.request_id = request_id
        self.setWindowTitle(f"Kích hoạt {APP_NAME}")
        self.setModal(True)
        self.setMinimumWidth(510)

        layout = QVBoxLayout(self)
        title = QLabel("KÍCH HOẠT ỨNG DỤNG")
        title.setStyleSheet("font-size: 20px; font-weight: 800; color: #39d8ff;")
        layout.addWidget(title)
        layout.addWidget(QLabel("Sao chép Request ID và gửi cho nhà cung cấp để nhận mã kích hoạt 16 chữ số."))

        request_row = QHBoxLayout()
        request_box = QLineEdit(request_id)
        request_box.setReadOnly(True)
        request_box.setStyleSheet("font-family: Consolas; font-size: 15px;")
        copy_button = QPushButton("Sao chép ID")
        copy_button.clicked.connect(self._copy_request_id)
        request_row.addWidget(request_box, 1)
        request_row.addWidget(copy_button)
        layout.addLayout(request_row)

        layout.addWidget(QLabel("Mã kích hoạt:"))
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("0000-0000-0000-0000")
        self.code_input.setMaxLength(19)
        self.code_input.setStyleSheet("font-family: Consolas; font-size: 17px;")
        self.code_input.textChanged.connect(self._format_code)
        self.code_input.returnPressed.connect(self._activate)
        layout.addWidget(self.code_input)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #ff7892;")
        layout.addWidget(self.status_label)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        close_button = QPushButton("Thoát")
        close_button.clicked.connect(self.reject)
        activate_button = QPushButton("Kích hoạt")
        activate_button.setDefault(True)
        activate_button.clicked.connect(self._activate)
        buttons.addWidget(close_button)
        buttons.addWidget(activate_button)
        layout.addLayout(buttons)
        self.code_input.setFocus()

    def _copy_request_id(self) -> None:
        QApplication.clipboard().setText(self.request_id)
        self.status_label.setStyleSheet("color: #65e6a7;")
        self.status_label.setText("Đã sao chép Request ID.")

    def _format_code(self, value: str) -> None:
        formatted = format_activation_code(value)
        if formatted != value:
            self.code_input.blockSignals(True)
            self.code_input.setText(formatted)
            self.code_input.setCursorPosition(len(formatted))
            self.code_input.blockSignals(False)

    def _activate(self) -> None:
        code = self.code_input.text()
        if not is_valid_activation_code(self.request_id, code):
            self.status_label.setStyleSheet("color: #ff7892;")
            expiry = activation_expiry(code)
            if expiry is not None and expiry < datetime.now().date():
                self.status_label.setText("Mã kích hoạt đã hết hạn.")
            else:
                self.status_label.setText("Mã kích hoạt không đúng với máy này.")
            return
        try:
            save_activation(config_dir(), self.request_id, code)
        except OSError as exc:
            self.status_label.setText(f"Không thể lưu kích hoạt: {exc}")
            return
        expiry = activation_expiry(code)
        QMessageBox.information(
            self,
            "Kích hoạt thành công",
            f"Ứng dụng đã được kích hoạt đến hết ngày {expiry.strftime('%d/%m/%Y')}.",
        )
        self.accept()


def main() -> int:
    instance_mutex = None
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
            instance_mutex = ctypes.windll.kernel32.CreateMutexW(
                None, False, "Local\\TIMKEM.VoiceOverStudio.MainApp"
            )
            if ctypes.windll.kernel32.GetLastError() == 183:
                ctypes.windll.user32.MessageBoxW(
                    None,
                    f"{APP_NAME} is already starting or running.",
                    APP_NAME,
                    0x40,
                )
                return 0
        except Exception:
            pass
    apply_settings()
    log_event("APP | started")
    log_event("APP | persistent log: " + str(log_path()))
    log_event("APP | GPU snapshot: " + gpu_snapshot())
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    if APP_ICON.is_file():
        app.setWindowIcon(QIcon(str(APP_ICON)))
    splash = None
    if os.environ.get("QT_QPA_PLATFORM", "").lower() != "offscreen":
        splash = create_startup_splash()
        splash.show()
        app.processEvents()
    app.setStyleSheet(
        """
        QMainWindow#mainWindow { background: #0b0f15; }
        QWidget#appRoot { background: #0b0f15; }
        QWidget { background: #0b0f15; color: #e7edf5; }
        QGroupBox { border: 1px solid #303947; border-radius: 6px; margin-top: 10px; padding-top: 8px; }
        QGroupBox::title { color: #39d8ff; subcontrol-origin: margin; left: 8px; }
        QLineEdit, QPlainTextEdit, QComboBox, QTableWidget {
            background: #171d27; border: 1px solid #303947; border-radius: 4px; padding: 4px;
        }
        QSpinBox, QDoubleSpinBox {
            background: #171d27; border: 1px solid #303947; border-radius: 4px;
            padding: 4px 24px 4px 4px;
        }
        QSpinBox::up-button, QDoubleSpinBox::up-button {
            subcontrol-origin: border; subcontrol-position: top right; width: 20px;
            background: #273142; border-left: 1px solid #344156; border-bottom: 1px solid #344156;
        }
        QSpinBox::down-button, QDoubleSpinBox::down-button {
            subcontrol-origin: border; subcontrol-position: bottom right; width: 20px;
            background: #273142; border-left: 1px solid #344156;
        }
        QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
        QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover { background: #3a4a64; }
        QPushButton { background: #273142; border: 1px solid #344156; border-radius: 5px; padding: 6px 10px; }
        QPushButton:hover { background: #334159; }
        QPushButton:disabled { color: #697386; background: #171d27; }
        QCheckBox { spacing: 8px; color: #e7edf5; }
        QCheckBox:disabled { color: #8290a3; }
        QCheckBox::indicator {
            width: 16px; height: 16px; border: 2px solid #91a4bd;
            border-radius: 4px; background: #171d27;
        }
        QCheckBox::indicator:hover { border-color: #39d8ff; background: #202b3a; }
        QCheckBox::indicator:checked {
            border-color: #39d8ff; background: #18bcd6;
        }
        QCheckBox::indicator:checked:disabled {
            border-color: #5a7187; background: #397889;
        }
        QHeaderView::section { background: #202735; color: #dbe5f0; padding: 6px; border: 0; }
        QTableWidget::item:selected { background: #123b4a; color: #20d9ff; }
        QTabWidget::pane { border: 0; top: -1px; }
        QTabBar::tab { background: #171d27; padding: 9px 18px; margin-right: 3px; border-radius: 5px; }
        QTabBar::tab:selected { color: #39d8ff; border: 1px solid #18aaca; }
        QWidget#windowBrand { background: #0b0f15; }
        QLabel#windowBrandTitle {
            color: #f5fbff; font-size: 14px; font-weight: 800; padding-right: 4px;
        }
        QPushButton#windowControlButton {
            background: #171d27; border: 1px solid #303947; border-radius: 5px;
            color: #dce8f4; padding: 0; font-weight: 800;
        }
        QPushButton#windowControlButton:hover { background: #273142; border-color: #39d8ff; }
        QPushButton#windowCloseButton {
            background: #2b1720; border: 1px solid #583040; border-radius: 5px;
            color: #ffd9e4; padding: 0; font-weight: 800;
        }
        QPushButton#windowCloseButton:hover { background: #b32645; border-color: #ff7892; color: #ffffff; }
        QProgressBar { border: 1px solid #303947; border-radius: 4px; text-align: center; }
        QProgressBar::chunk { background: #18bcd6; }
        """
    )
    request_id = hardware_request_id()
    if not is_activated(config_dir(), request_id):
        if splash:
            splash.hide()
        activation_dialog = ActivationDialog(request_id)
        if activation_dialog.exec() != QDialog.DialogCode.Accepted:
            return 0
        if splash:
            splash.show()
            app.processEvents()
    window = MainWindow()
    window.show()
    if splash:
        splash.finish(window)
    return app.exec()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
