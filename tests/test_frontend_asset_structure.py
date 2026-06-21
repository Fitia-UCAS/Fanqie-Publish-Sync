from __future__ import annotations

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT_DIR / "frontend"


def test_frontend_core_scripts_are_split_from_app_shell() -> None:
    core_dir = FRONTEND_DIR / "assets" / "core"
    assert (core_dir / "page_registry.js").exists()
    assert (core_dir / "form_controls.js").exists()
    assert (core_dir / "task_panel.js").exists()
    assert (core_dir / "state_store.js").exists()
    assert len((FRONTEND_DIR / "assets" / "app.js").read_text(encoding="utf-8").splitlines()) < 460


def test_frontend_page_files_use_page_object_names() -> None:
    page_dir = FRONTEND_DIR / "assets" / "pages"
    expected_pages = {
        "fanqie_publisher",
        "fanqie_syncer",
    }
    assert {path.stem for path in page_dir.glob("*.js")} == expected_pages


def test_frontend_core_scripts_load_before_app_shell() -> None:
    bundle = (FRONTEND_DIR / "assets" / "bundle.js").read_text(encoding="utf-8")
    app_start = bundle.index("const { pageTitles, defaultPage } = window.NovelConstants")
    assert bundle.index("window.NovelConstants") < app_start
    assert bundle.index("window.NovelTaskStateStore") < bundle.index("window.NovelTaskPanelMethods")
    assert bundle.index("window.renderFanqiePublisherPage") < app_start
    assert bundle.index("window.renderFanqieSyncerPage") < app_start


def test_header_has_separate_reset_data_and_authorization_buttons() -> None:
    html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    app_js = (FRONTEND_DIR / "assets" / "app.js").read_text(encoding="utf-8")

    assert 'id="resetDataButton"' in html
    assert 'id="loginButton"' in html
    assert 'reset_app_data' in app_js
    assert 'reset_login' in app_js

def test_console_open_directory_uses_feature_data_roots_from_state() -> None:
    task_panel_js = (FRONTEND_DIR / "assets" / "core" / "task_panel.js").read_text(encoding="utf-8")

    assert "statePath(key)" in task_panel_js
    assert "auto_publish: 'fanqie_publisher'" in task_panel_js
    assert "chapter_sync: 'fanqie_syncer'" in task_panel_js
    assert "this.statePath('auto_publish_logs')" not in task_panel_js
    assert "this.statePath('chapter_sync_logs')" not in task_panel_js
    assert "|| 'novel_process_outputs'" not in task_panel_js
    assert "|| 'novel_crawl_outputs'" not in task_panel_js


def test_common_buttons_use_consistent_height_tokens() -> None:
    css = (FRONTEND_DIR / "assets" / "styles.css").read_text(encoding="utf-8")

    assert "--control-height: 40px" in css
    assert "--control-small-height: 32px" in css
    assert "--button-height: var(--control-height)" in css
    assert "--button-small-height: var(--control-small-height)" in css
    assert ".primary-btn, .soft-btn, .ghost-btn, .mini-btn" in css
    assert "height: var(--button-height)" in css
    assert "height: var(--control-height)" in css
    assert ".terminal-clear, .terminal-copy, .terminal-open, .terminal-open-log, .terminal-open-backup" in css
    assert "height: var(--button-small-height)" in css


def test_frontend_task_state_store_is_loaded_before_task_panel() -> None:
    html = (FRONTEND_DIR / "assets" / "bundle.js").read_text(encoding="utf-8")
    store_js = (FRONTEND_DIR / "assets" / "core" / "state_store.js").read_text(encoding="utf-8")
    task_panel_js = (FRONTEND_DIR / "assets" / "core" / "task_panel.js").read_text(encoding="utf-8")
    app_js = (FRONTEND_DIR / "assets" / "app.js").read_text(encoding="utf-8")

    assert html.index("window.NovelTaskStateStore") < html.index("window.NovelTaskPanelMethods")
    assert "NovelTaskStateStore" in store_js
    assert "applyTaskEvent(event)" in task_panel_js
    assert "terminal-metrics" not in task_panel_js
    assert "taskStore:" in app_js


def test_parameter_controls_share_global_control_height() -> None:
    css = (FRONTEND_DIR / "assets" / "styles.css").read_text(encoding="utf-8")

    assert "--control-height: 40px" in css
    assert ".input, .select, .textarea" in css
    assert ".file-picker" in css
    assert ".start-btn" in css
    assert "height: var(--control-height)" in css
    assert "min-height: var(--control-height)" in css
    assert "height: 48px" not in css
    assert "height: 60px" not in css


def test_controls_and_buttons_share_font_size_token() -> None:
    css = (FRONTEND_DIR / "assets" / "styles.css").read_text(encoding="utf-8")

    assert "--control-font-size: 12px" in css
    assert ".input, .select, .textarea" in css
    assert ".primary-btn, .soft-btn, .ghost-btn, .mini-btn" in css
    assert "font-size: var(--control-font-size)" in css
    assert "font-size: 11.5px" not in css
    assert "font-size: 10.5px" not in css


def test_panels_use_flat_shared_surface_style() -> None:
    css = (FRONTEND_DIR / "assets" / "styles.css").read_text(encoding="utf-8")

    assert ".terminal-card" in css
    assert ".card, .fanqie-settings-card" in css
    assert "box-shadow: none" in css
    assert "status-panel .terminal-log" not in css


def test_output_panel_uses_time_and_complete_log_without_dynamic_status_bar() -> None:
    css = (FRONTEND_DIR / "assets" / "styles.css").read_text(encoding="utf-8")
    task_panel_js = (FRONTEND_DIR / "assets" / "core" / "task_panel.js").read_text(encoding="utf-8")

    assert "--output-panel-height" in css
    assert "--settings-panel-height" in css
    assert "terminal-status" not in task_panel_js
    assert "运行日志" in task_panel_js
    assert "log-label" not in task_panel_js
    assert "event.displayMessage" in task_panel_js
    assert "line.append(time, message, repeat)" in task_panel_js
    assert "log-repeat" in task_panel_js
    assert "terminal-metrics" not in css
    assert "terminal-metrics" not in task_panel_js
    assert "阶段：等待" not in task_panel_js
    assert "抓取：0" not in task_panel_js
    assert "写入：0" not in task_panel_js


def test_primary_task_buttons_share_icon_action_markup() -> None:
    page_dir = FRONTEND_DIR / "assets" / "pages"
    publisher_js = (page_dir / "fanqie_publisher.js").read_text(encoding="utf-8")
    syncer_js = (page_dir / "fanqie_syncer.js").read_text(encoding="utf-8")

    for page_js in [publisher_js, syncer_js]:
        assert "big-action primary-action" in page_js

    assert "primary-btn full-btn start-btn" not in publisher_js
    assert "<span>↑</span><div><b>启动发布</b></div>" in publisher_js


def test_action_buttons_use_exact_shared_control_height() -> None:
    css = (FRONTEND_DIR / "assets" / "styles.css").read_text(encoding="utf-8")

    assert "--control-icon-size: 24px" in css
    assert ".big-action {" in css
    assert "height: var(--button-height);" in css
    assert "min-height: var(--button-height);" in css
    assert ".compact-actions .big-action, .wide-action" in css
    assert "grid-template-columns: var(--control-icon-size) minmax(0, 1fr);" in css
    assert "box-shadow: none" in css

def test_pages_share_same_workspace_layout_tokens() -> None:
    css = (FRONTEND_DIR / "assets" / "styles.css").read_text(encoding="utf-8")

    assert "--workspace-width: 1200px" in css
    assert "--workspace-left-width: 400px" in css
    assert "--workspace-gap: 26px" in css
    assert "--page-gutter: 64px" in css
    assert "width: min(var(--workspace-width), calc(100% - var(--page-gutter)))" in css
    assert "grid-template-columns: var(--workspace-left-width) minmax(0, 1fr)" in css
    assert "gap: var(--workspace-gap)" in css
    assert "calc(100vw - 64px)" not in css
    assert "width: calc(100vw - 36px)" not in css


def test_page_host_reserves_scrollbar_space_to_prevent_page_switch_shift() -> None:
    css = (FRONTEND_DIR / "assets" / "styles.css").read_text(encoding="utf-8")

    assert ".page-host" in css
    assert "overflow-y: scroll" in css
    assert "scrollbar-gutter: stable both-edges" in css
    assert "padding: var(--page-vertical-padding) 0" in css


def test_control_fonts_share_one_weight_and_size_token() -> None:
    css = (FRONTEND_DIR / "assets" / "styles.css").read_text(encoding="utf-8")

    assert "--control-font-weight: 900" in css
    assert "font-weight: var(--control-font-weight)" in css
    assert "--control-font-weight: var(--control-font-weight)" not in css
