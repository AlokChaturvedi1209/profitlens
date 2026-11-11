"""Standalone scheduled monitoring process; safe to run separately from API."""
import os,time
from sqlalchemy import select
from .core import Base,engine,SessionLocal,Workspace
from .analytics import detect_alerts
from .seed import seed_demo

def run_once():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_demo(db)
        for workspace in db.scalars(select(Workspace)).all():
            try:
                new=detect_alerts(db,workspace.id,notify=not workspace.is_demo)
                print(f'Workspace {workspace.id}: {len(new)} new alerts',flush=True)
            except Exception as e:
                db.rollback();print(f'Alert scan failed workspace {workspace.id}: {type(e).__name__}',flush=True)

if __name__=='__main__':
    interval=max(60,int(os.getenv('MONITOR_INTERVAL_SECONDS','900')))
    while True:
        run_once();time.sleep(interval)
