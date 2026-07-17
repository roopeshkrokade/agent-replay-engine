import os
import json
from datetime import datetime
from sqlalchemy import create_engine, Column, String, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker

from .encoder import IRJSONEncoder
from ir import ExecutionGraph, ExecutionNode, ExecutionEdge, NodeKind, EdgeKind

Base = declarative_base()

class GraphRecord(Base):
    """SQLAlchemy Model for the 'execution_graphs' table."""
    __tablename__ = "execution_graphs"

    id = Column(String, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    data = Column(Text, nullable=False)


def _parse_enum(enum_cls, val):
    """Helper to safely parse an Enum from either its string name or integer value."""
    if isinstance(val, str) and val in enum_cls.__members__:
        return enum_cls[val]
    return enum_cls(val)


class SQLiteGraphStore:
    """Writes to a local SQLite database instead of separate JSON files."""
    
    def __init__(self, db_path: str = ".agent-replay/traces.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        self.db_uri = f"sqlite:///{db_path}"
        self.engine = create_engine(self.db_uri, connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def save(self, graph: ExecutionGraph):
        session = self.Session()
        try:
            graph_json = json.dumps(graph, cls=IRJSONEncoder)
            
            record = session.query(GraphRecord).filter_by(id=graph.id).first()
            if record:
                record.data = graph_json
            else:
                record = GraphRecord(id=graph.id, data=graph_json)
                session.add(record)
            
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def list_graphs(self):
        """Returns a list of all saved execution graphs (id and timestamp)."""
        session = self.Session()
        try:
            records = session.query(GraphRecord).order_by(GraphRecord.created_at.desc()).all()
            return [{"id": r.id, "created_at": r.created_at.isoformat()} for r in records]
        finally:
            session.close()

    def load(self, graph_id: str) -> ExecutionGraph:
        session = self.Session()
        try:
            record = session.query(GraphRecord).filter_by(id=graph_id).first()
            if not record:
                raise ValueError(f"Graph '{graph_id}' not found in database.")
            
            raw_data = json.loads(record.data)
            
            # 1. Reconstruct Nodes & NodeKinds
            if "nodes" in raw_data:
                for k, v in raw_data["nodes"].items():
                    if isinstance(v, dict):
                        if "kind" in v:
                            v["kind"] = _parse_enum(NodeKind, v["kind"])
                        raw_data["nodes"][k] = ExecutionNode(**v)
                        
            # 2. Reconstruct Edges & EdgeKinds
            if "edges" in raw_data:
                for k, v in raw_data["edges"].items():
                    if isinstance(v, dict):
                        if "kind" in v:
                            v["kind"] = _parse_enum(EdgeKind, v["kind"])
                        raw_data["edges"][k] = ExecutionEdge(**v)
            
            # The resolution_map remains a pure dictionary parsed from JSON
            return ExecutionGraph(**raw_data)
        finally:
            session.close()