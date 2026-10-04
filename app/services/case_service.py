class CaseService:
    """Cases are supplied by the caller, not built in.

    A case is the unseen scenario an apprentice works through. It arrives with the
    session that uses it and is stored on that session, so the catalogue is whatever
    the organisation has actually defined rather than a hardcoded fixture.
    """

    @staticmethod
    def normalise(case_id: str, case_data: dict) -> dict:
        return {"case_id": case_id, **(case_data or {})}
