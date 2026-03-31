"""
Worker de expiración de IPs.
Corre en segundo plano y marca como 'expiradas' las IPs cuyo TTL ha vencido.
"""
import time
from datetime import datetime
from app.db.database import SessionLocal
from app.db.esquemas import TablaIP

def run():
    while True:
        db = SessionLocal()
        now = datetime.utcnow()

        registros = db.query(TablaIP).filter(TablaIP.expira_en != None).all()

        for r in registros:
            if r.expira_en and r.expira_en < now:
                r.estado = "expirada"

        db.commit()
        db.close()
        time.sleep(60)

if __name__ == "__main__":
    print("Worker de expiración iniciado...")
    run()