def ingest_manual_study_note(source_type: str, raw_text: str) -> dict:
    # TODO(v1-phase4): call study workflow and persist session/task artifacts.
    return {"status": "accepted", "source_type": source_type, "chars": len(raw_text)}
