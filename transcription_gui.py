#!/usr/bin/env python3
"""Simple Qt GUI for offline audio/video transcription with faster-whisper."""

from __future__ import annotations

import sys
import traceback
import multiprocessing
import math
from pathlib import Path

try:
    from PySide6.QtCore import QObject, QRectF, QThread, QTimer, Qt, QUrl, Signal, Slot
    from PySide6.QtGui import (
        QCloseEvent,
        QColor,
        QDesktopServices,
        QDragEnterEvent,
        QDropEvent,
        QGuiApplication,
        QIcon,
        QPainter,
    )
    from PySide6.QtWidgets import (
        QApplication,
        QComboBox,
        QFileDialog,
        QFrame,
        QHBoxLayout,
        QLabel,
        QMainWindow,
        QMessageBox,
        QProgressBar,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )
except ModuleNotFoundError as exc:
    if exc.name == "PySide6":
        print(
            "Missing dependency: PySide6.\n"
            "Install with:\n"
            "  python3 -m pip install PySide6",
            file=sys.stderr,
        )
        raise SystemExit(1)
    raise

from transcription_cli import transcribe_with_faster_whisper

PRESETS: dict[str, tuple[str, str]] = {
    "High": ("large-v3", "accurate"),
    "Medium": ("small", "balanced"),
    "Low": ("base", "fast"),
}
SUPPORTED_INPUT_EXTENSIONS = (".mp3", ".mp4")


def user_model_cache_dir() -> Path:
    return (
        Path.home()
        / "Library"
        / "Application Support"
        / "faster_whisper_transcriber"
        / "models"
        / "faster-whisper"
    )


def app_log_path() -> Path:
    return Path.home() / "Library" / "Logs" / "faster_whisper_transcriber" / "startup.log"


def app_icon_path() -> Path | None:
    candidates: list[Path] = [Path(__file__).resolve().parent / "resources" / "app_icon.png"]
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates.extend(
            [
                exe_dir.parent / "Resources" / "resources" / "app_icon.png",
                exe_dir.parent / "Resources" / "app_icon.png",
            ]
        )
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "resources" / "app_icon.png")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


class AnimatedRobotBadge(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("robotBadge")
        self.setFixedSize(120, 120)
        self._phase = 0.0
        self._working = False
        self._timer = QTimer(self)
        self._timer.setInterval(33)  # ~30 FPS
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    @Slot(bool)
    def set_working(self, working: bool) -> None:
        self._working = working
        self.update()

    @Slot()
    def _tick(self) -> None:
        self._phase += 0.14 if self._working else 0.08
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)

        size = 16.0
        scale = min(self.width(), self.height()) / size
        ox = (self.width() - size * scale) / 2.0
        bob_amp = 0.7 if self._working else 0.45
        bob_speed = 2.4 if self._working else 1.7
        bob = math.sin(self._phase * bob_speed) * bob_amp
        oy = (self.height() - size * scale) / 2.0 + (bob * scale)
        painter.translate(ox, oy)
        painter.scale(scale, scale)

        # Soft pulse glow
        pulse_speed = 2.8 if self._working else 1.3
        pulse = (math.sin(self._phase * pulse_speed) + 1.0) * 0.5
        halo_base = 42 if self._working else 28
        halo_span = 38 if self._working else 24
        halo_alpha = int(halo_base + pulse * halo_span)
        painter.setBrush(QColor(0, 245, 212, halo_alpha))
        painter.drawRoundedRect(QRectF(1.2, 1.2, 13.6, 13.6), 3.0, 3.0)

        # Head
        painter.setBrush(QColor("#5FD0FF"))
        painter.drawRoundedRect(QRectF(2.8, 3.0, 10.4, 8.6), 2.0, 2.0)

        # Visor
        painter.setBrush(QColor("#162235"))
        painter.drawRoundedRect(QRectF(4.0, 5.2, 8.0, 3.2), 1.4, 1.4)

        # Blink animation
        blink_rate = 0.95 if self._working else 0.45
        blink_cycle = (self._phase * blink_rate) % 1.0
        eye_open = 1.0
        if blink_cycle > 0.88:
            x = (blink_cycle - 0.88) / 0.12
            eye_open = 0.14 + 0.86 * abs(1.0 - 2.0 * x)
        eye_h = 1.3 * eye_open
        eye_y = 6.0 + (1.3 - eye_h) / 2.0
        painter.setBrush(QColor("#00F5D4"))
        painter.drawRoundedRect(QRectF(5.2, eye_y, 1.3, eye_h), 0.55, 0.55)
        painter.drawRoundedRect(QRectF(9.5, eye_y, 1.3, eye_h), 0.55, 0.55)

        # Mouth
        painter.setBrush(QColor("#203654"))
        painter.drawRoundedRect(QRectF(6.1, 8.9, 3.8, 0.9), 0.4, 0.4)

        # Antenna wobble
        antenna_speed = 4.0 if self._working else 2.2
        antenna_amp = 0.46 if self._working else 0.32
        antenna_wobble = math.sin(self._phase * antenna_speed) * antenna_amp
        painter.save()
        painter.translate(8.0, 3.5)
        painter.rotate(antenna_wobble * 12.0)
        painter.setBrush(QColor("#DDF4FF"))
        painter.drawRoundedRect(QRectF(-0.4, -1.7, 0.8, 1.7), 0.3, 0.3)
        painter.setBrush(QColor("#FF6B9A"))
        painter.drawEllipse(QRectF(-0.9, -2.7, 1.8, 1.8))
        painter.restore()

        # Base
        painter.setBrush(QColor("#203654"))
        painter.drawRoundedRect(QRectF(4.6, 11.5, 6.8, 2.0), 0.8, 0.8)

        # Side bolts
        painter.setBrush(QColor("#DDF4FF"))
        painter.drawEllipse(QRectF(2.0, 7.2, 0.9, 0.9))
        painter.drawEllipse(QRectF(13.1, 7.2, 0.9, 0.9))


def log_startup_error(exc: BaseException) -> None:
    log_file = app_log_path()
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as fh:
        fh.write("\n=== Startup failed ===\n")
        fh.write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))


def bundled_model_cache_dir() -> Path | None:
    if not getattr(sys, "frozen", False):
        return None

    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "models" / "faster-whisper")

    exe_dir = Path(sys.executable).resolve().parent
    candidates.append(exe_dir / "models" / "faster-whisper")
    candidates.append(exe_dir.parent / "Frameworks" / "models" / "faster-whisper")
    candidates.append(exe_dir.parent / "Resources" / "models" / "faster-whisper")

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def model_exists_in_cache(model_name: str, cache_dir: Path) -> bool:
    repo_dir = cache_dir / f"models--Systran--faster-whisper-{model_name}"
    return repo_dir.exists()


class DropArea(QFrame):
    fileDropped = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setObjectName("dropArea")
        self.setMinimumHeight(130)
        self.setCursor(Qt.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        self.label = QLabel("Drop your MP3/MP4 file here (offline, stays on your Mac)")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setWordWrap(True)
        layout.addWidget(self.label)

    def set_text(self, text: str) -> None:
        self.label.setText(text)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if self._first_supported_path(event) is not None:
            event.acceptProposedAction()
            self.setProperty("active", True)
            self.style().polish(self)
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        path = self._first_supported_path(event)
        if path is None:
            event.ignore()
            return
        self.fileDropped.emit(path)
        self.setProperty("active", False)
        self.style().polish(self)
        event.acceptProposedAction()

    def dragLeaveEvent(self, _event) -> None:  # noqa: N802
        self.setProperty("active", False)
        self.style().polish(self)

    def _first_supported_path(self, event: QDragEnterEvent | QDropEvent) -> str | None:
        urls = event.mimeData().urls()
        for url in urls:
            if not url.isLocalFile():
                continue
            file_path = url.toLocalFile()
            if Path(file_path).suffix.lower() in SUPPORTED_INPUT_EXTENSIONS:
                return file_path
        return None


class TranscribeWorker(QObject):
    finished = Signal(str)
    failed = Signal(str)
    cancelled = Signal()
    progress = Signal(int)

    def __init__(
        self,
        audio_path: Path,
        model: str,
        mode: str,
        model_cache_dir: Path,
        language: str,
    ) -> None:
        super().__init__()
        self.audio_path = audio_path
        self.model = model
        self.mode = mode
        self.model_cache_dir = model_cache_dir
        self.language = language
        self._cancel_requested = False

    @Slot()
    def request_cancel(self) -> None:
        self._cancel_requested = True

    @Slot()
    def run(self) -> None:
        try:
            self.model_cache_dir.mkdir(parents=True, exist_ok=True)
            text = transcribe_with_faster_whisper(
                audio_path=self.audio_path,
                language=self.language,
                prompt=None,
                model_name=self.model,
                mode=self.mode,
                model_cache_dir=self.model_cache_dir,
                local_files_only=True,
                cancel_check=lambda: self._cancel_requested,
                progress_callback=self.progress.emit,
            )
            if not text:
                raise RuntimeError("Empty transcription.")
            self.finished.emit(text)
        except InterruptedError:
            self.cancelled.emit()
        except Exception as exc:
            self.failed.emit(str(exc))


class ModelCheckWorker(QObject):
    finished = Signal(bool, str)
    failed = Signal(str)

    def __init__(self, model: str, cache_dir: Path, models: list[str] | None = None) -> None:
        super().__init__()
        self.model = model
        self.cache_dir = cache_dir
        self.models = models

    @Slot()
    def run(self) -> None:
        try:
            targets = self.models if self.models else [self.model]
            self.cache_dir.mkdir(parents=True, exist_ok=True)

            for target in targets:
                if model_exists_in_cache(target, self.cache_dir):
                    continue

                from faster_whisper import WhisperModel  # type: ignore

                _ = WhisperModel(
                    target,
                    device="cpu",
                    compute_type="int8_float32",
                    download_root=str(self.cache_dir),
                    local_files_only=False,
                )

            if len(targets) > 1:
                self.finished.emit(True, "Model downloads completed.")
            else:
                self.finished.emit(True, "Model download completed.")
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Faster Whisper Transcriber")
        self._set_window_icon()

        self.thread: QThread | None = None
        self.worker: TranscribeWorker | None = None
        self.model_thread: QThread | None = None
        self.model_worker: ModelCheckWorker | None = None
        self.audio_path: Path | None = None
        self.current_model_cache_path: Path = user_model_cache_dir()
        self.last_transcription_text: str | None = None
        self.last_output_path: Path | None = None

        container = QWidget()
        self.setCentralWidget(container)
        root = QVBoxLayout(container)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)

        hero = QFrame()
        hero.setObjectName("heroPanel")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(14, 12, 14, 12)
        hero_layout.setSpacing(10)

        self.robot_badge = AnimatedRobotBadge()

        title = QLabel("Faster Whisper Transcriber")
        title.setObjectName("title")
        subtitle = QLabel(
            "Offline AI: transcribes MP3/MP4 locally, without sending data to the cloud."
        )
        subtitle.setObjectName("subtitle")
        self.requirements_label = QLabel(
            "<b>Requirements</b> · Minimum: macOS / Windows / Linux, 8 GB RAM, ~7 GB free disk. "
            "Recommended for long files: modern 4+ core CPU (or compatible GPU), 16 GB RAM, Medium/Low preset."
        )
        self.requirements_label.setObjectName("heroRequirements")
        self.requirements_label.setWordWrap(True)
        self.requirements_label.setTextFormat(Qt.RichText)

        title_col = QVBoxLayout()
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setSpacing(6)
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        title_col.addWidget(self.requirements_label)

        hero_layout.addWidget(self.robot_badge, 0)
        hero_layout.addLayout(title_col, 1)

        self.drop_area = DropArea()
        self.drop_area.fileDropped.connect(self._set_audio_path)

        browse_btn = QPushButton("Choose MP3/MP4 file")
        browse_btn.setObjectName("secondary")
        browse_btn.setMinimumHeight(44)
        browse_btn.clicked.connect(self.pick_audio)

        preset_label = QLabel("Reliability")
        preset_label.setObjectName("selectorLabel")
        self.preset_combo = QComboBox()
        self.preset_combo.setObjectName("selectorCombo")
        self.preset_combo.setFixedHeight(36)
        self.preset_combo.addItems(["High", "Medium", "Low"])
        self.preset_combo.setCurrentText("Medium")
        self.preset_combo.currentTextChanged.connect(self._refresh_model_status)

        lang_label = QLabel("Language")
        lang_label.setObjectName("selectorLabel")
        self.lang_combo = QComboBox()
        self.lang_combo.setObjectName("selectorCombo")
        self.lang_combo.setFixedHeight(36)
        self.lang_combo.addItem("Italian", "it")
        self.lang_combo.addItem("English", "en")
        self.lang_combo.setCurrentIndex(0)

        preset_layout = QVBoxLayout()
        preset_layout.setContentsMargins(0, 0, 0, 0)
        preset_layout.setSpacing(4)
        preset_layout.addWidget(preset_label)
        preset_layout.addWidget(self.preset_combo)

        lang_layout = QVBoxLayout()
        lang_layout.setContentsMargins(0, 0, 0, 0)
        lang_layout.setSpacing(4)
        lang_layout.addWidget(lang_label)
        lang_layout.addWidget(self.lang_combo)

        selectors_row = QHBoxLayout()
        selectors_row.setSpacing(8)
        selectors_row.addLayout(preset_layout, 1)
        selectors_row.addLayout(lang_layout, 1)

        model_path_title = QLabel("Model folder")
        model_path_title.setObjectName("selectorLabel")
        self.model_path_label = QLabel("<a href=\"open_models_folder\">Open model folder</a>")
        self.model_path_label.setObjectName("path")
        self.model_path_label.setTextFormat(Qt.RichText)
        self.model_path_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.model_path_label.setOpenExternalLinks(False)
        self.model_path_label.linkActivated.connect(lambda _link: self.open_model_folder())
        self._set_model_cache_path(self.current_model_cache_path)
        model_path_row = QHBoxLayout()
        model_path_row.setSpacing(8)
        model_path_row.addWidget(self.model_path_label, 1)

        model_status_title = QLabel("Model")
        model_status_title.setObjectName("selectorLabel")
        self.model_status_label = QLabel("Model status: -")
        self.model_status_label.setObjectName("modelStatus")
        self.check_models_button = QPushButton("Check model")
        self.check_models_button.setObjectName("secondary")
        self.check_models_button.setMinimumHeight(38)
        self.check_models_button.clicked.connect(self.check_or_download_model)
        model_status_row = QHBoxLayout()
        model_status_row.setSpacing(8)
        model_status_row.addWidget(self.model_status_label, 1)
        model_status_row.addWidget(self.check_models_button)

        model_path_col = QVBoxLayout()
        model_path_col.setContentsMargins(0, 0, 0, 0)
        model_path_col.setSpacing(4)
        model_path_col.addWidget(model_path_title)
        model_path_col.addLayout(model_path_row)

        model_status_col = QVBoxLayout()
        model_status_col.setContentsMargins(0, 0, 0, 0)
        model_status_col.setSpacing(4)
        model_status_col.addWidget(model_status_title)
        model_status_col.addLayout(model_status_row)

        model_tools_row = QHBoxLayout()
        model_tools_row.setSpacing(8)
        model_tools_row.addLayout(model_path_col, 1)
        model_tools_row.addLayout(model_status_col, 1)

        self.start_button = QPushButton("Start transcription")
        self.start_button.setObjectName("primary")
        self.start_button.setMinimumHeight(44)
        self.start_button.clicked.connect(self.start_transcription)
        self.stop_button = QPushButton("Stop")
        self.stop_button.setObjectName("danger")
        self.stop_button.setMinimumHeight(44)
        self.stop_button.clicked.connect(self.stop_transcription)
        self.stop_button.setEnabled(False)

        self.download_button = QPushButton("Download transcription")
        self.download_button.setObjectName("secondary")
        self.download_button.setMinimumHeight(44)
        self.download_button.clicked.connect(self.download_transcript)
        self.download_button.setEnabled(False)

        controls_row = QHBoxLayout()
        controls_row.setSpacing(10)
        controls_row.setContentsMargins(0, 0, 0, 0)
        controls_row.addWidget(self.start_button, 2)
        controls_row.addWidget(self.stop_button, 1)
        controls_row.addWidget(self.download_button, 1)

        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("status")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.setFormat("%p%")

        root.addWidget(hero)
        root.addWidget(self.drop_area)
        root.addWidget(browse_btn)
        root.addLayout(selectors_row)
        root.addLayout(model_tools_row)
        root.addLayout(controls_row)
        root.addWidget(self.status_label)
        root.addWidget(self.progress)
        root.addStretch(1)

        self._apply_styles()
        self._refresh_model_status()
        self._apply_smart_fixed_size()

    def _apply_smart_fixed_size(self) -> None:
        # Dimensione basata sul contenuto, limitata in modo ragionevole dallo schermo.
        hint = self.sizeHint()
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            self.setFixedSize(max(hint.width(), 760), max(hint.height(), 520))
            return

        available = screen.availableGeometry()
        min_w, min_h = 760, 520
        max_w = int(available.width() * 0.9)
        max_h = int(available.height() * 0.9)
        target_w = max(min_w, min(hint.width() + 40, max_w))
        target_h = max(min_h, min(hint.height() + 40, max_h))
        self.setFixedSize(target_w, target_h)

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f6f9fc, stop:1 #eef3f8);
            }
            QWidget {
                color: #0f172a;
                font-size: 14px;
                font-family: "SF Pro Text", "Segoe UI", "Helvetica Neue", sans-serif;
            }
            #heroPanel {
                background: #ffffff;
                border: 1px solid #d8e1eb;
                border-radius: 14px;
            }
            #robotBadge {
                background: #f8fbff;
                border: 1px solid #d8e1eb;
                border-radius: 10px;
            }
            #title { font-size: 28px; font-weight: 700; color: #0f172a; letter-spacing: 0.4px; }
            #subtitle { color: #475569; margin-bottom: 2px; }
            #heroRequirements {
                color: #334155;
                font-size: 12px;
                background: #f8fbff;
                border: 1px solid #dbeafe;
                border-radius: 8px;
                padding: 6px 8px;
            }
            #status { color: #0f766e; font-weight: 600; }
            #path {
                color: #1d4ed8;
                font-size: 13px;
                font-weight: 600;
                padding: 8px 0 6px 0;
            }
            #path a {
                color: #1d4ed8;
                text-decoration: underline;
            }
            #modelStatus {
                color: #0f766e;
                background: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 10px;
                padding: 8px 10px;
                min-height: 22px;
            }
            #modelStatus[available=\"true\"] {
                color: #166534;
                background: #f0fdf4;
                border-color: #86efac;
            }
            #modelStatus[available=\"false\"] {
                color: #92400e;
                background: #fffbeb;
                border-color: #fcd34d;
            }
            #selectorLabel {
                color: #334155;
                font-size: 12px;
                font-weight: 600;
            }
            #dropArea {
                background: #fbfdff;
                border: 2px dashed #93c5fd;
                border-radius: 12px;
                color: #1e293b;
            }
            #dropArea[active=\"true\"], #dropArea:hover {
                background: #eff6ff;
                border: 2px solid #2563eb;
            }
            QComboBox {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 10px;
                padding: 8px 10px;
                min-height: 36px;
            }
            QComboBox:hover { border-color: #94a3b8; }
            QComboBox:focus { border-color: #2563eb; }
            QComboBox::drop-down { border: none; width: 28px; }
            QComboBox QAbstractItemView {
                background: #ffffff;
                color: #0f172a;
                border: 1px solid #cbd5e1;
                selection-background-color: #dbeafe;
                selection-color: #0f172a;
            }
            QComboBox#selectorCombo {
                min-height: 38px;
                font-weight: 600;
                padding-right: 8px;
            }
            QComboBox#selectorCombo::drop-down {
                border-left: 1px solid #e2e8f0;
                width: 28px;
            }
            QPushButton {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 10px;
                padding: 10px 14px;
                min-height: 44px;
                min-width: 120px;
                font-weight: 600;
                letter-spacing: 0.2px;
                color: #0f172a;
            }
            QPushButton:hover { background: #f8fafc; border-color: #94a3b8; }
            QPushButton:pressed { background: #f1f5f9; }
            QPushButton:disabled { background: #f1f5f9; color: #94a3b8; border-color: #e2e8f0; }
            QPushButton#secondary {
                background: #f8fbff;
                border-color: #bfdbfe;
                color: #1e3a8a;
            }
            QPushButton#secondary:hover { background: #eff6ff; border-color: #93c5fd; }
            QPushButton#primary {
                background: #2563eb;
                border-color: #1d4ed8;
                color: #ffffff;
                font-weight: 700;
            }
            QPushButton#primary:hover { background: #1d4ed8; border-color: #1e40af; }
            QPushButton#primary:pressed { background: #1e40af; }
            QPushButton#danger {
                background: #fff1f2;
                border-color: #fecdd3;
                color: #be123c;
            }
            QPushButton#danger:hover { background: #ffe4e6; border-color: #fda4af; }
            QPushButton#danger:pressed { background: #fecdd3; }
            QProgressBar {
                background: #e2e8f0;
                border-radius: 7px;
                border: 1px solid #d1dae6;
                height: 14px;
                color: #1e293b;
                text-align: center;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #0ea5e9);
                border-radius: 7px;
            }
            """
        )

    def _set_window_icon(self) -> None:
        icon_file = app_icon_path()
        if icon_file is None:
            return
        icon = QIcon(str(icon_file))
        self.setWindowIcon(icon)

    def _show_themed_message(self, title: str, message: str, kind: str = "info") -> None:
        accents = {
            "info": "#2563eb",
            "success": "#16a34a",
            "error": "#dc2626",
        }
        icons = {
            "info": QMessageBox.Information,
            "success": QMessageBox.Information,
            "error": QMessageBox.Critical,
        }
        accent = accents.get(kind, accents["info"])
        box = QMessageBox(self)
        box.setIcon(icons.get(kind, QMessageBox.Information))
        box.setWindowTitle(title)
        box.setText(message)
        box.setStandardButtons(QMessageBox.Ok)
        box.setStyleSheet(
            f"""
            QMessageBox {{
                background-color: #ffffff;
                color: #0f172a;
                border: 1px solid {accent};
                border-radius: 12px;
            }}
            QMessageBox QWidget {{
                background-color: #ffffff;
            }}
            QMessageBox QDialogButtonBox {{
                background-color: #ffffff;
            }}
            QMessageBox QLabel {{
                color: #0f172a;
                background: transparent;
            }}
            QMessageBox QPushButton {{
                background: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 8px 14px;
                color: #0f172a;
            }}
            QMessageBox QPushButton:hover {{ background: #f1f5f9; }}
            """
        )
        text_label = box.findChild(QLabel, "qt_msgbox_label")
        if text_label is not None:
            text_label.setMinimumWidth(360)
            text_label.setWordWrap(True)
            text_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        icon_label = box.findChild(QLabel, "qt_msgboxex_icon_label")
        if icon_label is not None:
            icon_label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        box.exec()

    def _show_themed_info(self, title: str, message: str, success: bool = False) -> None:
        kind = "success" if success else "info"
        self._show_themed_message(title, message, kind=kind)

    def _show_themed_error(self, title: str, message: str) -> None:
        self._show_themed_message(title, message, kind="error")

    def _set_busy(self, busy: bool) -> None:
        self.start_button.setEnabled(not busy)
        self.check_models_button.setEnabled(not busy)
        self.stop_button.setEnabled(busy)
        self.robot_badge.set_working(busy)
        if busy:
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
            self.status_label.setText("Transcription in progress... 0%")
        else:
            self.progress.setRange(0, 100)
            self.progress.setValue(100 if self.last_transcription_text else 0)

    def _selected_model(self) -> tuple[str, str, str]:
        preset_name = self.preset_combo.currentText()
        model, mode = PRESETS[preset_name]
        return preset_name, model, mode

    def _resolve_model_cache(self, model: str) -> tuple[Path, bool]:
        bundled_cache = bundled_model_cache_dir()
        if bundled_cache and model_exists_in_cache(model, bundled_cache):
            return bundled_cache, True

        user_cache = user_model_cache_dir()
        return user_cache, model_exists_in_cache(model, user_cache)

    def _set_model_cache_path(self, path: Path) -> None:
        self.current_model_cache_path = path
        self.model_path_label.setToolTip("Open model folder")

    @Slot()
    def _refresh_model_status(self) -> None:
        _preset, model, _mode = self._selected_model()
        cache_dir, available = self._resolve_model_cache(model)
        self._set_model_cache_path(cache_dir)
        if available:
            self.model_status_label.setText("Model status: available")
        else:
            self.model_status_label.setText("Model status: missing")
        self.model_status_label.setProperty("available", available)
        self.model_status_label.style().unpolish(self.model_status_label)
        self.model_status_label.style().polish(self.model_status_label)

    @Slot()
    def pick_audio(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select audio/video file",
            str(Path.cwd()),
            "Supported audio/video (*.mp3 *.mp4)",
        )
        if not path:
            return
        self._set_audio_path(path)

    @Slot(str)
    def _set_audio_path(self, path: str) -> None:
        selected = Path(path)
        self.audio_path = selected
        self.drop_area.set_text(f"Selected file:\n{selected.name}")
        self.status_label.setText(f"Output: {selected.with_suffix('.txt').name}")

    @Slot()
    def start_transcription(self) -> None:
        if self.thread and self.thread.isRunning():
            self._show_themed_info("In progress", "A transcription is already running.")
            return

        if self.audio_path is None:
            self._show_themed_error(
                "Missing input",
                "Load an MP3 or MP4 file (drag & drop or button).",
            )
            return

        if not self.audio_path.exists():
            self._show_themed_error("File not found", f"File not found:\n{self.audio_path}")
            return

        preset_name, model, mode = self._selected_model()
        language = self.lang_combo.currentData() or "it"
        model_cache, available = self._resolve_model_cache(model)
        if not available:
            self._show_themed_error(
                "Model missing",
                "The selected model is not available.\nUse 'Check model' before starting.",
            )
            self._refresh_model_status()
            return

        self._set_model_cache_path(model_cache)
        self.last_transcription_text = None
        self.last_output_path = self.audio_path.with_suffix(".txt")
        self.download_button.setEnabled(False)

        self.worker = TranscribeWorker(
            audio_path=self.audio_path,
            model=model,
            mode=mode,
            model_cache_dir=model_cache,
            language=language,
        )
        self.thread = QThread(self)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._on_done)
        self.worker.cancelled.connect(self._on_cancelled)
        self.worker.failed.connect(self._on_error)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self.thread.quit)
        self.worker.cancelled.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.finished.connect(self.thread.deleteLater)

        self._set_busy(True)
        self.thread.start()

    @Slot()
    def stop_transcription(self) -> None:
        if not self.thread or not self.thread.isRunning() or not self.worker:
            return
        self.worker.request_cancel()
        self.thread.quit()
        self.stop_button.setEnabled(False)
        self.status_label.setText("Stopping...")

    @Slot(str)
    def _on_done(self, transcript_text: str) -> None:
        self.last_transcription_text = transcript_text
        self.download_button.setEnabled(True)
        suggested_name = self.last_output_path.name if self.last_output_path else "file.txt"
        self.status_label.setText("Transcription completed (not saved yet)")
        self._show_themed_info(
            "Completed",
            f"Transcription completed.\nUse 'Download transcription' to save it (suggested: {suggested_name}).",
            success=True,
        )
        self._clear_worker()
        self._refresh_model_status()

    @Slot(str)
    def _on_error(self, error_text: str) -> None:
        self.status_label.setText("Error during transcription")
        self._show_themed_error("Error", error_text)
        self._clear_worker()
        self._refresh_model_status()

    @Slot()
    def _on_cancelled(self) -> None:
        self.status_label.setText("Transcription stopped")
        self._show_themed_info("Stopped", "Transcription stopped by the user.")
        self._clear_worker()

    @Slot(int)
    def _on_progress(self, value: int) -> None:
        bounded = max(0, min(100, value))
        self.progress.setValue(bounded)
        self.status_label.setText(f"Transcription in progress... {bounded}%")

    def _set_model_check_busy(self, busy: bool, status_text: str, progress_value: int | None = None) -> None:
        self.start_button.setEnabled(not busy)
        self.check_models_button.setEnabled(not busy)
        self.status_label.setText(status_text)
        if busy:
            self.progress.setRange(0, 0)
            return
        self.progress.setRange(0, 100)
        if progress_value is not None:
            self.progress.setValue(progress_value)

    def _clear_model_worker(self) -> None:
        if self.model_thread:
            try:
                if self.model_thread.isRunning():
                    self.model_thread.quit()
                    self.model_thread.wait(1500)
            except RuntimeError:
                # Evita crash se il QThread e gia stato eliminato da Qt.
                pass
        self.model_thread = None
        self.model_worker = None

    @Slot()
    def check_or_download_model(self) -> None:
        if self.model_thread:
            try:
                if self.model_thread.isRunning():
                    self._show_themed_info("In progress", "Model check is already running.")
                    return
            except RuntimeError:
                self.model_thread = None
                self.model_worker = None

        _preset_name, model, _mode = self._selected_model()
        cache_dir, available = self._resolve_model_cache(model)
        self._set_model_cache_path(cache_dir)
        if available:
            self._refresh_model_status()
            self._show_themed_info(
                "Model available",
                "The selected model is already available.",
                success=True,
            )
            return

        self.model_worker = ModelCheckWorker(model=model, cache_dir=cache_dir)
        self.model_thread = QThread(self)
        self.model_worker.moveToThread(self.model_thread)
        self.model_thread.started.connect(self.model_worker.run)
        self.model_worker.finished.connect(self._on_model_check_done)
        self.model_worker.failed.connect(self._on_model_check_error)
        self.model_worker.finished.connect(self.model_thread.quit)
        self.model_worker.failed.connect(self.model_thread.quit)
        self.model_thread.finished.connect(self.model_thread.deleteLater)

        self._set_model_check_busy(True, "Model download in progress...")
        self.model_thread.start()

    @Slot(bool, str)
    def _on_model_check_done(self, _ok: bool, message: str) -> None:
        self._set_model_check_busy(False, message, progress_value=100)
        self._refresh_model_status()
        self._clear_model_worker()
        self._show_themed_info("Models", message, success=True)

    @Slot(str)
    def _on_model_check_error(self, error_text: str) -> None:
        self._set_model_check_busy(False, "Error during model check", progress_value=0)
        self._refresh_model_status()
        self._clear_model_worker()
        self._show_themed_error("Model check error", error_text)

    @Slot()
    def open_model_folder(self) -> None:
        path = self.current_model_cache_path
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    @Slot()
    def download_transcript(self) -> None:
        if not self.last_transcription_text or not self.last_output_path:
            self._show_themed_info("No transcription", "Run a transcription first.")
            return

        suggested = str(self.last_output_path)
        selected_path, _ = QFileDialog.getSaveFileName(
            self,
            "Download transcription",
            suggested,
            "Text (*.txt)",
        )
        if not selected_path:
            return

        save_path = Path(selected_path)
        if save_path.suffix.lower() != ".txt":
            save_path = save_path.with_suffix(".txt")
        save_path.write_text(self.last_transcription_text + "\n", encoding="utf-8")
        self._show_themed_info("Saved", f"Transcription saved to:\n{save_path}", success=True)

    def _clear_worker(self) -> None:
        # Resetta thread/worker cosi lo start riparte sempre.
        self._set_busy(False)
        self.stop_button.setEnabled(False)
        if self.thread:
            self.thread.quit()
            self.thread.wait(1500)
            self.thread = None
        self.worker = None

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self.thread and self.thread.isRunning():
            self._show_themed_info(
                "Transcription in progress",
                "Wait for transcription to finish before closing the app.",
            )
            event.ignore()
            return
        model_thread_running = False
        if self.model_thread:
            try:
                model_thread_running = self.model_thread.isRunning()
            except RuntimeError:
                self.model_thread = None
                self.model_worker = None
        if model_thread_running:
            self._show_themed_info(
                "Model check in progress",
                "Wait for model check to finish before closing the app.",
            )
            event.ignore()
            return

        if self.thread:
            self.thread.quit()
            self.thread.wait(1500)
        self._clear_model_worker()
        event.accept()


def main() -> int:
    try:
        multiprocessing.freeze_support()
        app = QApplication(sys.argv)
        icon_file = app_icon_path()
        if icon_file is not None:
            app.setWindowIcon(QIcon(str(icon_file)))
        window = MainWindow()
        window.show()
        return app.exec()
    except Exception as exc:
        log_startup_error(exc)
        try:
            QMessageBox.critical(
                None,
                "App startup error",
                f"The app could not start.\nDetails: {app_log_path()}",
            )
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
