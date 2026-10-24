from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import flet as ft
import flet_camera as fc

from journal_store import JournalEntry, JournalStore


PAPER = "#F7F6F2"
CARD = "#FCFBF8"
INK = "#2B2D2B"
MUTED = "#74776F"
SAGE = "#768A76"
SAGE_DARK = "#526652"
STONE = "#D8D5C9"
SAGE_PALE = "#E7EBE4"
CAMERA_BG = "#171A16"


def _image_extension(filename: str, contents: bytes) -> str:
    if contents.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if contents.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if contents.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if contents.startswith(b"BM"):
        return ".bmp"
    if contents.startswith(b"RIFF") and contents[8:12] == b"WEBP":
        return ".webp"
    suffix = Path(filename).suffix.lower()
    return suffix if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"} else ".jpg"


async def main(page: ft.Page) -> None:
    # Use Flet's app-private data directory on device and the local journal
    # directory during development. This avoids a native-only StoragePaths call
    # when the same app is opened through Flet's web development server.
    store = JournalStore()
    store.cleanup_unreferenced_images()

    today = date.today()
    today_key = today.isoformat()
    today_entry = store.get_entry(today_key)
    saved_text = today_entry.text_content if today_entry else ""
    saved_image_path = today_entry.image_path if today_entry else None
    draft_image_path = saved_image_path
    selected_tab = 0

    page.title = "Stitch"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(
        color_scheme_seed=SAGE,
        scrollbar_theme=ft.ScrollbarTheme(thickness=0),
    )
    page.bgcolor = PAPER
    page.padding = 0
    page.spacing = 0
    navigation_bar = ft.NavigationBar(
        selected_index=0,
        bgcolor=CARD,
        indicator_color=SAGE_PALE,
        destinations=[
            ft.NavigationBarDestination(
                icon=ft.Icons.TODAY_OUTLINED,
                selected_icon=ft.Icons.TODAY,
                label="Today",
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.HISTORY_OUTLINED,
                selected_icon=ft.Icons.HISTORY,
                label="History",
            ),
        ],
        on_change=lambda e: on_navigation_change(e),
    )
    page.navigation_bar = navigation_bar

    content_host = ft.Container(expand=True)
    photo_slot = ft.Container()
    camera_control: fc.Camera | None = None
    camera_actions_host = ft.Container(
        alignment=ft.Alignment.CENTER,
        padding=ft.Padding.only(top=6, bottom=8),
    )
    camera_photo: bytes | None = None
    camera_ready = False
    camera_busy = False
    camera_capturing = False
    camera_error: str | None = None
    save_status = ft.Text(size=12, color=MUTED)
    text_field = ft.TextField(
        value=saved_text,
        hint_text="A thought, a detail, a little win…",
        multiline=True,
        min_lines=4,
        max_lines=6,
        max_length=140,
        counter=None,
        filled=True,
        fill_color=CARD,
        border_color=STONE,
        focused_border_color=SAGE,
        border_radius=16,
        content_padding=16,
        text_size=16,
        color=INK,
        cursor_color=SAGE,
        autocorrect=True,
        on_change=lambda e: on_text_change(e),
    )
    save_button = ft.FilledButton(
        content="Save today's entry",
        icon=ft.Icons.DONE,
        expand=True,
        on_click=lambda e: save_today(e),
        style=ft.ButtonStyle(
            bgcolor=SAGE_DARK,
            color=CARD,
            padding=ft.Padding.symmetric(horizontal=22, vertical=16),
            shape=ft.RoundedRectangleBorder(radius=14),
        ),
    )
    file_picker = ft.FilePicker()
    page.services.append(file_picker)

    def on_navigation_change(e: ft.Event[ft.NavigationBar]) -> None:
        nonlocal selected_tab
        selected_tab = e.control.selected_index or 0
        render_content()

    def on_text_change(_: ft.Event[ft.TextField]) -> None:
        update_save_state()

    def update_save_state() -> None:
        current_text = text_field.value or ""
        is_dirty = current_text != saved_text or draft_image_path != saved_image_path
        if is_dirty:
            save_status.value = "Unsaved changes"
            save_status.color = SAGE_DARK
        elif today_entry:
            save_status.value = "Saved on this device"
            save_status.color = MUTED
        else:
            save_status.value = "Your entry stays on this device"
            save_status.color = MUTED
        save_button.content = "Save changes" if today_entry else "Save today's entry"

    def show_message(message: str) -> None:
        page.show_dialog(ft.SnackBar(content=ft.Text(message)))

    def render_photo_slot() -> None:
        if draft_image_path:
            image_bytes = store.read_image(draft_image_path)
        else:
            image_bytes = None

        if image_bytes:
            photo_slot.content = ft.Row(
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=14,
                controls=[
                    ft.Container(
                        width=92,
                        height=92,
                        border_radius=14,
                        clip_behavior=ft.ClipBehavior.HARD_EDGE,
                        content=ft.Image(
                            src=image_bytes,
                            width=92,
                            height=92,
                            fit=ft.BoxFit.COVER,
                        ),
                    ),
                    ft.Column(
                        expand=True,
                        spacing=8,
                        controls=[
                            ft.Text("A moment, kept.", size=14, weight=ft.FontWeight.W_600, color=INK),
                            ft.OutlinedButton(
                                content=ft.Text("Change photo", size=12),
                                icon=ft.Icons.PHOTO_LIBRARY_OUTLINED,
                                on_click=show_photo_options,
                            ),
                        ],
                    ),
                    ft.IconButton(
                        icon=ft.Icons.CLOSE,
                        icon_color=MUTED,
                        tooltip="Remove photo",
                        on_click=remove_draft_image,
                    ),
                ],
            )
        else:
            photo_slot.content = ft.OutlinedButton(
                content="Add a photo",
                icon=ft.Icons.ADD_A_PHOTO_OUTLINED,
                on_click=show_photo_options,
                style=ft.ButtonStyle(
                    color=SAGE_DARK,
                    padding=ft.Padding.symmetric(horizontal=18, vertical=14),
                    shape=ft.RoundedRectangleBorder(radius=12),
                ),
            )

    def render_content() -> None:
        if selected_tab == 0:
            content_host.content = build_today_view()
        else:
            content_host.content = build_history_view()
        page.update()

    def build_camera_actions() -> ft.Control:
        if camera_photo:
            return ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                spacing=14,
                controls=[
                    ft.Text(
                        "Keep this moment?",
                        size=16,
                        weight=ft.FontWeight.W_600,
                        color=CARD,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Row(
                        spacing=12,
                        controls=[
                            ft.OutlinedButton(
                                content="Retake",
                                icon=ft.Icons.REPLAY,
                                expand=True,
                                on_click=retake_camera_photo,
                                style=ft.ButtonStyle(
                                    color=CARD,
                                    side=ft.BorderSide(1, "#879181"),
                                    padding=ft.Padding.symmetric(vertical=15),
                                    shape=ft.RoundedRectangleBorder(radius=14),
                                ),
                            ),
                            ft.FilledButton(
                                content="Use photo",
                                icon=ft.Icons.CHECK,
                                expand=True,
                                on_click=use_camera_photo,
                                style=ft.ButtonStyle(
                                    bgcolor=SAGE,
                                    color=CARD,
                                    padding=ft.Padding.symmetric(vertical=15),
                                    shape=ft.RoundedRectangleBorder(radius=14),
                                ),
                            ),
                        ],
                    ),
                ],
            )

        shutter = ft.Container(
            width=76,
            height=76,
            border_radius=38,
            bgcolor=SAGE if camera_ready and not camera_busy else "#43483F",
            alignment=ft.Alignment.CENTER,
            on_click=capture_camera_photo if camera_ready and not camera_busy else None,
            content=ft.Icon(
                ft.Icons.PHOTO_CAMERA_OUTLINED,
                size=34,
                color=CARD if camera_ready and not camera_busy else "#A5AAA0",
            ),
        )
        return ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
            controls=[
                shutter,
                ft.Text(
                    "Taking your photo…"
                    if camera_capturing
                    else "Camera unavailable"
                    if camera_error
                    else "Tap to capture"
                    if camera_ready
                    else "Preparing your camera…",
                    size=13,
                    color="#D2D6CE",
                ),
            ],
        )

    def refresh_camera_ui() -> None:
        if camera_control:
            if camera_photo:
                camera_control.content = ft.Container(
                    expand=True,
                    alignment=ft.Alignment.CENTER,
                    bgcolor=CAMERA_BG,
                    content=ft.Image(src=camera_photo, expand=True, fit=ft.BoxFit.CONTAIN),
                )
            elif camera_busy:
                camera_control.content = ft.Container(
                    expand=True,
                    alignment=ft.Alignment.CENTER,
                    bgcolor=CAMERA_BG,
                    content=ft.Column(
                        tight=True,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=12,
                        controls=[
                            ft.ProgressRing(color=SAGE_PALE),
                            ft.Text(
                                "Taking your photo…" if camera_capturing else "Opening camera…",
                                color=CARD,
                                size=14,
                            ),
                        ],
                    ),
                )
            elif camera_error:
                camera_control.content = ft.Container(
                    expand=True,
                    alignment=ft.Alignment.CENTER,
                    bgcolor=CAMERA_BG,
                    padding=24,
                    content=ft.Text(
                        camera_error,
                        color=CARD,
                        size=14,
                        text_align=ft.TextAlign.CENTER,
                    ),
                )
            else:
                camera_control.content = None
        camera_actions_host.content = build_camera_actions()

    def build_camera_view() -> ft.Control:
        refresh_camera_ui()
        return ft.Container(
            expand=True,
            bgcolor=CAMERA_BG,
            padding=ft.Padding.symmetric(horizontal=0, vertical=12),
            content=ft.Column(
                expand=True,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                spacing=12,
                controls=[
                    ft.Row(
                        spacing=12,
                        controls=[
                            ft.IconButton(
                                icon=ft.Icons.CLOSE,
                                icon_color=CARD,
                                bgcolor="#2A3029",
                                tooltip="Close camera",
                                on_click=close_camera,
                            ),
                            ft.Column(
                                expand=True,
                                spacing=2,
                                controls=[
                                    ft.Text(
                                        "TAKE A PHOTO",
                                        size=11,
                                        weight=ft.FontWeight.BOLD,
                                        color="#B9C2B3",
                                    ),
                                    ft.Text(
                                        "A moment, kept.",
                                        size=18,
                                        weight=ft.FontWeight.W_600,
                                        color=CARD,
                                    ),
                                ],
                            ),
                        ],
                    ),
                    ft.Container(
                        expand=True,
                        bgcolor="#0E100E",
                        content=camera_control,
                    ),
                    camera_actions_host,
                ],
            ),
        )

    async def open_camera() -> None:
        nonlocal camera_control, camera_photo, camera_ready, camera_busy, camera_error
        camera_control = fc.Camera(expand=True, preview_enabled=True)
        camera_control.on_state_change = on_camera_state_change
        camera_photo = None
        camera_ready = False
        camera_busy = True
        camera_error = None
        page.bgcolor = CAMERA_BG
        page.navigation_bar = None
        content_host.content = build_camera_view()
        page.update()

        try:
            cameras = await camera_control.get_available_cameras()
            if not cameras:
                raise RuntimeError("No camera was found on this device.")
            selected_camera = next(
                (camera for camera in cameras if camera.lens_direction == fc.CameraLensDirection.BACK),
                cameras[0],
            )
            await camera_control.initialize(
                description=selected_camera,
                resolution_preset=fc.ResolutionPreset.MEDIUM,
                enable_audio=False,
                image_format_group=fc.ImageFormatGroup.JPEG,
            )
            if camera_error:
                raise RuntimeError(camera_error)
            camera_busy = False
            camera_ready = True
            refresh_camera_ui()
            page.update()
        except Exception as exc:
            close_camera()
            show_message(f"Couldn't open the camera: {exc}")

    async def on_camera_state_change(e: fc.CameraStateEvent) -> None:
        nonlocal camera_ready, camera_busy, camera_error
        if not e.has_error:
            return
        camera_error = e.error_description or "The camera preview could not start."
        camera_ready = False
        camera_busy = False
        refresh_camera_ui()
        page.update()

    async def capture_camera_photo(_: ft.Event[ft.Control] | None = None) -> None:
        nonlocal camera_photo, camera_busy, camera_capturing
        if not camera_control or not camera_ready or camera_busy:
            return
        camera_busy = True
        camera_capturing = True
        refresh_camera_ui()
        page.update()
        try:
            camera_photo = await camera_control.take_picture()
            if not camera_photo:
                show_message("The camera did not return a photo. Please try again.")
        except Exception as exc:
            show_message(f"Couldn't capture the photo: {exc}")
        finally:
            camera_busy = False
            camera_capturing = False
            refresh_camera_ui()
            page.update()

    def retake_camera_photo(_: ft.Event[ft.Control]) -> None:
        nonlocal camera_photo
        camera_photo = None
        refresh_camera_ui()
        page.update()

    def use_camera_photo(_: ft.Event[ft.Control]) -> None:
        if not camera_photo:
            return
        try:
            relative_path = store.save_image(camera_photo, ".jpg")
        except Exception as exc:
            show_message(f"Couldn't keep that photo: {exc}")
            return
        close_camera()
        set_draft_image(relative_path)

    def close_camera(_: ft.Event[ft.Control] | None = None) -> None:
        nonlocal camera_control, camera_photo, camera_ready, camera_busy, camera_capturing, camera_error
        camera_control = None
        camera_photo = None
        camera_ready = False
        camera_busy = False
        camera_capturing = False
        camera_error = None
        page.bgcolor = PAPER
        page.navigation_bar = navigation_bar
        render_content()

    def build_today_view() -> ft.Control:
        mode_label = "TODAY'S PAGE" if not today_entry else "TODAY · EDITING"
        return ft.Column(
            expand=True,
            scroll=ft.ScrollMode.HIDDEN,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            spacing=0,
            controls=[
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=20, vertical=22),
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                        spacing=18,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Text("STITCH", size=14, weight=ft.FontWeight.BOLD, color=SAGE_DARK),
                                    ft.Text(today.strftime("%A, %d %B"), size=12, color=MUTED),
                                ],
                            ),
                            ft.Column(
                                spacing=7,
                                controls=[
                                    ft.Text("Keep the day\nin a line.", size=34, weight=ft.FontWeight.W_700, color=INK),
                                    ft.Text("One small note. A photo if you like. Just for you.", size=14, color=MUTED),
                                ],
                            ),
                            ft.Container(
                                bgcolor=CARD,
                                border_radius=22,
                                padding=20,
                                content=ft.Column(
                                    spacing=16,
                                    controls=[
                                        ft.Row(
                                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                            controls=[
                                                ft.Text(mode_label, size=10, weight=ft.FontWeight.BOLD, color=SAGE_DARK),
                                                ft.Icon(ft.Icons.WB_SUNNY_OUTLINED, color=SAGE, size=18),
                                            ],
                                        ),
                                        ft.Text("What do you want to remember?", size=17, weight=ft.FontWeight.W_600, color=INK),
                                        text_field,
                                        ft.Container(height=1, bgcolor=STONE),
                                        ft.Column(
                                            spacing=10,
                                            controls=[
                                                ft.Text("ADD A PHOTO", size=10, weight=ft.FontWeight.BOLD, color=SAGE_DARK),
                                                photo_slot,
                                            ],
                                        ),
                                        ft.Container(height=1, bgcolor=STONE),
                                        ft.Column(
                                            spacing=10,
                                            controls=[
                                                save_status,
                                                ft.Row(expand=True, controls=[save_button]),
                                            ],
                                        ),
                                    ],
                                ),
                            ),
                            ft.Row(
                                alignment=ft.MainAxisAlignment.CENTER,
                                spacing=7,
                                controls=[
                                    ft.Icon(ft.Icons.LOCK_OUTLINE, size=14, color=MUTED),
                                    ft.Text("Private by design · stored only on this device", size=11, color=MUTED),
                                ],
                            ),
                        ],
                    ),
                )
            ],
        )

    def build_history_view() -> ft.Control:
        entries = store.list_entries()
        heading = ft.Column(
            spacing=18,
            controls=[
                ft.Text("STITCH", size=14, weight=ft.FontWeight.BOLD, color=SAGE_DARK),
                ft.Column(
                    spacing=7,
                    controls=[
                        ft.Text("A life, in little moments.", size=29, weight=ft.FontWeight.W_700, color=INK),
                        ft.Text(
                            f"{len(entries)} {('entry' if len(entries) == 1 else 'entries')} saved",
                            size=14,
                            color=MUTED,
                        ),
                    ],
                ),
            ],
        )
        privacy_note = ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=7,
            controls=[
                ft.Icon(ft.Icons.LOCK_OUTLINE, size=14, color=MUTED),
                ft.Text("Your journal is stored only on this device", size=11, color=MUTED),
            ],
        )

        if not entries:
            empty_card = ft.Container(
                margin=ft.Margin.symmetric(horizontal=20),
                padding=28,
                bgcolor=CARD,
                border_radius=22,
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=10,
                    controls=[
                        ft.Icon(ft.Icons.AUTO_STORIES_OUTLINED, size=36, color=SAGE),
                        ft.Text("Your story starts today.", size=18, weight=ft.FontWeight.W_600, color=INK),
                        ft.Text(
                            "Save a line and it will be waiting here.",
                            size=14,
                            color=MUTED,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ],
                ),
            )
            return ft.Column(
                expand=True,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                spacing=0,
                controls=[
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=20, vertical=22),
                        content=heading,
                    ),
                    ft.Column(
                        expand=True,
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                        controls=[empty_card],
                    ),
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=20, vertical=18),
                        content=privacy_note,
                    ),
                ],
            )

        cards = [build_entry_card(entry) for entry in entries]
        return ft.Column(
            expand=True,
            scroll=ft.ScrollMode.HIDDEN,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            spacing=0,
            controls=[
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=20, vertical=22),
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                        spacing=22,
                        controls=[
                            heading,
                            ft.Column(spacing=12, controls=cards),
                            privacy_note,
                        ],
                    ),
                )
            ],
        )

    def build_entry_card(entry: JournalEntry) -> ft.Control:
        entry_date = date.fromisoformat(entry.entry_date)
        image_bytes = store.read_image(entry.image_path)
        date_badge = ft.Container(
            width=54,
            height=62,
            border_radius=14,
            bgcolor=SAGE_PALE,
            content=ft.Column(
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=1,
                controls=[
                    ft.Text(entry_date.strftime("%b").upper(), size=10, weight=ft.FontWeight.BOLD, color=SAGE_DARK),
                    ft.Text(entry_date.strftime("%d"), size=21, weight=ft.FontWeight.W_700, color=INK),
                ],
            ),
        )
        text_content = entry.text_content.strip() or "A photo from this day."
        row_controls: list[ft.Control] = [
            date_badge,
            ft.Column(
                expand=True,
                spacing=5,
                controls=[
                    ft.Text(entry_date.strftime("%A"), size=12, weight=ft.FontWeight.W_600, color=SAGE_DARK),
                    ft.Text(text_content, size=14, color=INK, max_lines=3, overflow=ft.TextOverflow.ELLIPSIS),
                ],
            ),
        ]
        if image_bytes:
            row_controls.append(
                ft.Container(
                    width=62,
                    height=62,
                    border_radius=12,
                    clip_behavior=ft.ClipBehavior.HARD_EDGE,
                    content=ft.Image(src=image_bytes, width=62, height=62, fit=ft.BoxFit.COVER),
                )
            )
        return ft.Container(
            padding=14,
            bgcolor=CARD,
            border_radius=18,
            content=ft.Row(spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=row_controls),
        )

    def show_photo_options(_: ft.Event[ft.Control] | None = None) -> None:
        async def choose_library(_: ft.Event[ft.Control]) -> None:
            page.pop_dialog()
            await pick_from_library()

        async def take_photo(_: ft.Event[ft.Control]) -> None:
            page.pop_dialog()
            await open_camera()

        page.show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text("Add a photo", color=INK),
                content=ft.Text("Choose a favorite or capture something now.", color=MUTED),
                actions=[
                    ft.OutlinedButton(
                        content="Photo library",
                        icon=ft.Icons.PHOTO_LIBRARY_OUTLINED,
                        on_click=choose_library,
                    ),
                    ft.FilledButton(
                        content="Take photo",
                        icon=ft.Icons.PHOTO_CAMERA_OUTLINED,
                        on_click=take_photo,
                    ),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
        )

    async def pick_from_library() -> None:
        try:
            picked_files = await file_picker.pick_files(
                dialog_title="Choose a journal photo",
                file_type=ft.FilePickerFileType.IMAGE,
                allow_multiple=False,
                with_data=True,
            )
            if not picked_files:
                return
            picked = picked_files[0]
            contents = getattr(picked, "bytes", None)
            if not contents and getattr(picked, "path", None):
                contents = Path(picked.path).read_bytes()
            if not contents:
                show_message("That photo could not be opened. Please choose another one.")
                return
            relative_path = store.save_image(contents, _image_extension(picked.name, contents))
            set_draft_image(relative_path)
        except Exception as exc:
            show_message(f"Couldn't add that photo: {exc}")

    def set_draft_image(relative_path: str) -> None:
        nonlocal draft_image_path
        previous_draft = draft_image_path
        draft_image_path = relative_path
        if previous_draft and previous_draft != saved_image_path and previous_draft != relative_path:
            store.delete_image(previous_draft)
        render_photo_slot()
        update_save_state()
        page.update()

    def remove_draft_image(_: ft.Event[ft.Control]) -> None:
        nonlocal draft_image_path
        previous_draft = draft_image_path
        draft_image_path = None
        if previous_draft and previous_draft != saved_image_path:
            store.delete_image(previous_draft)
        render_photo_slot()
        update_save_state()
        page.update()

    def save_today(_: ft.Event[ft.Control]) -> None:
        nonlocal today_entry, saved_text, saved_image_path, draft_image_path
        text = (text_field.value or "").strip()
        if not text and not draft_image_path:
            show_message("Write a line or add a photo before saving.")
            return
        try:
            previous_image_path = saved_image_path
            today_entry = store.save_entry(today_key, text, draft_image_path)
            saved_text = text
            text_field.value = text
            saved_image_path = today_entry.image_path
            draft_image_path = saved_image_path
            if previous_image_path and previous_image_path != saved_image_path:
                store.delete_image(previous_image_path)
            save_status.value = f"Saved at {datetime.now().astimezone().strftime('%H:%M')}"
            save_status.color = SAGE_DARK
            save_button.content = "Save changes"
            update_save_state()
            save_status.value = f"Saved at {datetime.now().astimezone().strftime('%H:%M')}"
            save_status.color = SAGE_DARK
            page.update()
        except Exception as exc:
            show_message(f"Couldn't save your entry: {exc}")

    update_save_state()
    render_photo_slot()
    content_host.content = build_today_view()
    page.add(ft.SafeArea(content=content_host, expand=True))
    page.update()


if __name__ == "__main__":
    ft.run(main)

