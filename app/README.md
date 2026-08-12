apps/
└── sample_NB/
    ├── README.md          ← this file
    └── app/
        ├── images/            ← ✏️  add an image/icon for the app (e.g. icons/canada_64.png)
        ├── app_sample_NB.py   ← ✏️  ENTRY POINT  (6 lines to edit per new app — see "❶ EDIT" block)
        ├── sample_nb.env      ← ✏️  ENV CONFIG   (set LOGS_PATH and extras here; optional, "" to skip)
        ├── sample_NB.py       ← ✏️  YOUR PAYLOAD (UI + logic — must define `render_run_page(sb)`)
        │
        ├── sandbox.py         ← 🔒  framework — do not edit
        ├── startup_sample_NB.py ← 🔒  framework — do not edit (customize welcome/about text only)
        └── logs.py            ← 🔒  framework — do not edit

## Framework: NiceGUI 3.0+

This app is built on the NiceGUI multi-tab architecture template (not Streamlit). The
entry point (`app_sample_NB.py`) dynamically imports your payload module and renders it
inside a `▶ Run` tab, alongside `🏠 Startup` and `📋 Logs` tabs.

## Payload contract

Your payload module (`sample_NB.py`, or your renamed equivalent) **must** define:

```python
def render_run_page(sb: Sandbox) -> None:
    ...  # build your UI here using nicegui.ui elements
```

`sb` is a `Sandbox` instance already bound to the current user/tenant session — do not
construct your own `Sandbox` inside the payload; use the one passed in.

Optionally, your payload may also define:

| Name | Purpose |
|---|---|
| `SESSION_DEFAULTS: dict` | Merged into the framework's base session defaults on load |
| `DATA_KEYS: list[str]` | Keys cleared by the 🗑 **Clear Data** button |
| `refresh_all(sb)` | Called after Clear Data / Reset Everything, to refresh any `@ui.refreshable` zones |

If the payload doesn't define `render_run_page(sb)`, `app_sample_NB.py` raises:
```
AttributeError: Payload module '<name>' must define `render_run_page(sb)`.
```

## ❶ EDIT block — the only lines you normally need to change

In `app_sample_NB.py`:

1. `_PAYLOAD_MODULE` – name of your feature module (no `.py`), e.g. `"sample_NB"`
2. `_APP_SLUG` – internal slug; used for log filename suffix + storage-secret default
3. `_APP_TITLE` – human-readable name shown in the info bar + browser title
4. `_APP_VERSION` – semver string shown on the Startup tab
5. `_ENV_FILENAME` – name of the `.env` file next to `app_sample_NB.py` (`""` to skip)
6. `_STANDALONE_PORT` – port used only by `python app_sample_NB.py` direct execution

## To test (standalone)

```bash
python apps/sample_NB/app/app_sample_NB.py
```

This starts a NiceGUI dev server (default `http://localhost:8082`, or whatever port you
set via `_STANDALONE_PORT` / the `PORT` env var) and serves the app at `/`.

## Embedded usage

When loaded from `landing_home.py`, the catalog calls:
```python
mod.main(username=..., tenant_id=...)
```
`main()` must **not** create `ui.header()` or `ui.left_drawer()` — those are top-level
layout elements and raise `RuntimeError` when nested inside the catalog's own layout.
The standalone `@ui.page("/")` handler at the bottom of `app_sample_NB.py` (guarded by
`if __name__ in {"__main__", "__mp_main__"}`) provides the header only for direct
execution, so importing this module never double-registers a `"/"` route.

