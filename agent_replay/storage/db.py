import os
import json
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker

from .encoder import IRJSONEncoder
from agent_replay.ir import (
    ExecutionGraph, ExecutionNode, ExecutionEdge, NodeKind, EdgeKind,
    GraphMetadata, NodeMetadata, EdgeMetadata,
)

Base = declarative_base()

class AgentRecord(Base):
    """SQLAlchemy Model for versioned agent executions."""
    __tablename__ = "agent_executions"

    record_id = Column(String, primary_key=True) # e.g. "weather_bot_v1.0.0"
    agent_id = Column(String, index=True, nullable=False)
    agent_name = Column(String, nullable=False)
    version = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)
    last_execution_timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    data = Column(Text, nullable=False)

class RecordedSpan(Base):
    """Raw OTel span received over OTLP, kept so graphs can be recompiled later."""
    __tablename__ = "recorded_spans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, index=True, nullable=False)
    received_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    data = Column(Text, nullable=False)

def _run_id(graph_json: str) -> Optional[str]:
    """The OTLP run a stored graph was compiled from (graphs recorded before OTel have none)."""
    try:
        return (json.loads(graph_json).get("metadata", {}).get("attributes") or {}).get("run_id")
    except (ValueError, AttributeError):
        return None

def _parse_enum(enum_cls, val):
    if isinstance(val, str) and val in enum_cls.__members__:
        return enum_cls[val]
    return enum_cls(val)

class SQLiteGraphStore:
    def __init__(self, db_path: str = ".agent-replay/traces.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_uri = f"sqlite:///{db_path}"
        self.engine = create_engine(self.db_uri, connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def _get_next_version(self, current_version: str) -> str:
        """Increments the major version (e.g., 1.0.0 -> 2.0.0)."""
        if not current_version:
            return "1.0.0"
        major = int(current_version.split('.')[0])
        return f"{major + 1}.0.0"

    def save(self, graph: ExecutionGraph, agent_id: str, agent_name: str) -> str:
        """Saves a NEW version of the agent's execution. Never overwrites."""
        session = self.Session()
        try:
            history = session.query(AgentRecord).filter_by(agent_id=agent_id).order_by(AgentRecord.last_execution_timestamp.desc()).all()
            now = datetime.utcnow()
            
            if history:
                latest = history[0]
                next_version = self._get_next_version(latest.version)
                original_created_at = latest.created_at
            else:
                next_version = "1.0.0"
                original_created_at = now

            record_id = f"{agent_id}_v{next_version}"
            graph_json = json.dumps(graph, cls=IRJSONEncoder)
            
            new_record = AgentRecord(
                record_id=record_id,
                agent_id=agent_id,
                agent_name=agent_name,
                version=next_version,
                created_at=original_created_at,
                last_execution_timestamp=now,
                data=graph_json
            )
            session.add(new_record)
            session.commit()
            return record_id
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def get_unique_agents(self) -> List[Dict]:
        """API Requirement 1: Return one entry per unique agent (latest version)."""
        session = self.Session()
        try:
            records = session.query(AgentRecord).order_by(AgentRecord.last_execution_timestamp.asc()).all()
            agents_map = {}
            for r in records:
                agents_map[r.agent_id] = {
                    "agent_id": r.agent_id,
                    "agent_name": r.agent_name,
                    "latest_version": r.version,
                    "created_at": r.created_at.isoformat(),
                    "last_execution_timestamp": r.last_execution_timestamp.isoformat()
                }
            return sorted(list(agents_map.values()), key=lambda x: x["last_execution_timestamp"], reverse=True)
        finally:
            session.close()

    def get_agent_history(self, agent_id: str) -> List[Dict]:
        """API Requirement 2: Return complete chronological version history for an agent."""
        session = self.Session()
        try:
            records = session.query(AgentRecord).filter_by(agent_id=agent_id).order_by(AgentRecord.last_execution_timestamp.asc()).all()
            return [{
                "record_id": r.record_id,
                "version": r.version,
                "created_at": r.created_at.isoformat(),
                "last_execution_timestamp": r.last_execution_timestamp.isoformat()
            } for r in records]
        finally:
            session.close()

    def load(self, record_id: str) -> ExecutionGraph:
        """Loads the raw graph data for a specific version record."""
        session = self.Session()
        try:
            record = session.query(AgentRecord).filter_by(record_id=record_id).first()
            if not record:
                raise ValueError(f"Record '{record_id}' not found.")
            
            raw_data = json.loads(record.data)
            
            if isinstance(raw_data.get("metadata"), dict):
                raw_data["metadata"] = GraphMetadata(**raw_data["metadata"])

            if "nodes" in raw_data:
                for k, v in raw_data["nodes"].items():
                    if isinstance(v, dict) and "kind" in v:
                        v["kind"] = _parse_enum(NodeKind, v["kind"])
                    if isinstance(v.get("metadata"), dict):
                        v["metadata"] = NodeMetadata(**v["metadata"])
                    raw_data["nodes"][k] = ExecutionNode(**v)
                        
            if "edges" in raw_data:
                for k, v in raw_data["edges"].items():
                    if isinstance(v, dict) and "kind" in v:
                        v["kind"] = _parse_enum(EdgeKind, v["kind"])
                    if isinstance(v.get("metadata"), dict):
                        v["metadata"] = EdgeMetadata(**v["metadata"])
                    raw_data["edges"][k] = ExecutionEdge(**v)
            
            return ExecutionGraph(**raw_data)
        finally:
            session.close()

    # ---------------------------------------------------------
    # SYSTEM MANAGEMENT METHODS (Restored!)
    # ---------------------------------------------------------
    def delete(self, record_id: str):
        """Remove a specific run from the database, with the raw spans it was compiled from."""
        session = self.Session()
        try:
            record = session.query(AgentRecord).filter_by(record_id=record_id).first()
            if record:
                run_id = _run_id(record.data)
                session.delete(record)
                if run_id:
                    session.query(RecordedSpan).filter_by(run_id=run_id).delete()
                session.commit()
        finally:
            session.close()

    def update_graph(self, record_id: str, graph: ExecutionGraph):
        """Replace a record's graph in place (same version), e.g. after recompiling or adding an entrypoint."""
        session = self.Session()
        try:
            record = session.query(AgentRecord).filter_by(record_id=record_id).first()
            if not record:
                raise ValueError(f"Record '{record_id}' not found.")
            record.data = json.dumps(graph, cls=IRJSONEncoder)
            session.commit()
        finally:
            session.close()

    def get_count(self) -> int:
        """Get the total number of recorded runs across all agents."""
        session = self.Session()
        try:
            return session.query(AgentRecord).count()
        finally:
            session.close()

    def clear_all(self):
        """Wipe all traces from the database."""
        session = self.Session()
        try:
            session.query(AgentRecord).delete()
            session.query(RecordedSpan).delete()
            session.commit()
        finally:
            session.close()

    # ---------------------------------------------------------
    # RAW SPAN METHODS (OTLP ingestion)
    # ---------------------------------------------------------
    def add_spans(self, run_id: str, spans: List[Dict]):
        session = self.Session()
        try:
            session.add_all([RecordedSpan(run_id=run_id, data=json.dumps(s, default=str)) for s in spans])
            session.commit()
        finally:
            session.close()

    def get_spans(self, run_id: str) -> List[Dict]:
        session = self.Session()
        try:
            rows = session.query(RecordedSpan).filter_by(run_id=run_id).order_by(RecordedSpan.id.asc()).all()
            return [json.loads(r.data) for r in rows]
        finally:
            session.close()

    def prune_spans(self, older_than: timedelta) -> int:
        """
        Delete raw spans no record refers to (runs that never ended, abandoned replays, spans
        without a run id) once they are older than `older_than`. Spans behind a record are kept
        for recompiling until the record is deleted.
        """
        session = self.Session()
        try:
            keep = {_run_id(data) for (data,) in session.query(AgentRecord.data).all()} - {None}
            cutoff = datetime.utcnow() - older_than
            query = session.query(RecordedSpan).filter(RecordedSpan.received_at < cutoff)
            if keep:
                query = query.filter(RecordedSpan.run_id.notin_(keep))
            removed = query.delete(synchronize_session=False)
            session.commit()
            return removed
        finally:
            session.close()

    def delete_spans(self, run_id: str):
        session = self.Session()
        try:
            session.query(RecordedSpan).filter_by(run_id=run_id).delete()
            session.commit()
        finally:
            session.close()