# Epic: Nice to Have Tools (Priority 3)

## Checklist

- [ ] **`translation`** — Text translation via LibreTranslate or DeepL API. Auto-detect source language.
- [ ] **`youtube`** — Extract transcript/subtitles from YouTube videos via `youtube-transcript-api` library.
- [ ] **`maps`** — Geocoding (address → coordinates) and reverse geocoding via OpenStreetMap Nominatim (free, no key).
- [ ] **`qrcode`** — Generate QR codes and barcodes. Pure Python: `qrcode` + `pillow` libraries. Output to MinIO/S3.

## New Dependencies
```txt
youtube-transcript-api  # youtube
qrcode, pillow           # qrcode
```

## Implementation Pattern
Each tool follows the standard 5-step pattern:
1. Create `backend/src/tools/TOOL_NAME.py` with `build_TOOL_NAME_tools(tool_config)` factory
2. Add type string to `VALID_TOOL_TYPES` in `backend/src/services/tool_service.py`
3. Create Alembic migration: `ALTER TYPE tool_type_enum ADD VALUE 'new_type'`
4. Add `elif tool.type == "new_type":` branch in `_build_tool_callables()` in `backend/src/agents/runner.py`
5. (Optional) Add config fields in `frontend/src/features/admin/resources/tools/ToolForm.tsx`

## Reference
Full details in `docs/planning/tools.md` → Nice to Have section.
