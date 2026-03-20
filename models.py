from typing import Optional

from sqlmodel import SQLModel, Field, create_engine


DATABASE_PATH = "incidents.db"


class Incident(SQLModel, table=True):
    incident_key: str = Field(primary_key=True)

    record_id: Optional[str] = None
    incident_date: Optional[str] = None
    time: Optional[str] = None
    division: Optional[str] = None
    title: Optional[str] = None
    location: Optional[str] = None
    summary: Optional[str] = None
    adults_arrested: Optional[str] = None
    pd_contact_number: Optional[str] = None
    source_url: Optional[str] = None
    raw_data: Optional[str] = None


engine = create_engine(f"sqlite:///{DATABASE_PATH}")
SQLModel.metadata.create_all(engine)
