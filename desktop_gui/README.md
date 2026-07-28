# Desktop GUI

This folder is the clean entry point for the PySide6 desktop version.

The actual GUI source code lives in `src/bank_parser/desktop` so it can reuse the same parser, validation, export, and enrichment code as the web app.

## Run

From the project root:

```powershell
.\desktop_gui\run_desktop.ps1
```

If PySide6 is not installed yet:

```powershell
.\.venv\Scripts\python.exe -m pip install PySide6
```

## Notes

- Warnings and errors are minimized by default.
- Use **Show all review flags** in the app only when you want the full review table.
- Excel export opens with a suggested file name automatically.
