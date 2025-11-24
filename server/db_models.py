from sqlalchemy import Column, String, Boolean, DateTime, Text, Integer
from datetime import datetime

try:
    from sqlalchemy.orm import declarative_base
except ImportError:
    from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Agent(Base):
    __tablename__ = 'agents'
    
    agent_id = Column(String, primary_key=True)
    alive = Column(Boolean, default=True)
    hostname = Column(String)
    last_seen = Column(DateTime, default=datetime.utcnow)
    first_seen = Column(DateTime, default=datetime.utcnow)
    total_heartbeats = Column(Integer, default=0)
    config = Column(Text)  # JSON serialized

class ModuleResult(Base):
    __tablename__ = 'module_results'
    
    id = Column(String, primary_key=True)
    agent_id = Column(String)
    request_id = Column(String)
    result_data = Column(Text)  # JSON serialized
    created_at = Column(DateTime, default=datetime.utcnow)

class ModuleState(Base):
    __tablename__ = 'module_states'
    
    request_id = Column(String, primary_key=True)
    agent_id = Column(String)
    module_name = Column(String)
    state = Column(String)
    error_message = Column(Text, nullable=True)
    details = Column(Text, nullable=True)  # JSON serialized
    timestamp = Column(DateTime, default=datetime.utcnow)